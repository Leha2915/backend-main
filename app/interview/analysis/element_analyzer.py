"""
Element Analyzer module for analyzing user inputs in the context of the ACV laddering model.
Specializes in identifying and categorizing elements like attributes, consequences, and values.
"""

import logging
from typing import Tuple, Dict, List, Any, Optional, Union

from app.llm.template_store import render_template
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree import Tree
from app.interview.interview_tree.tree_utils import TreeUtils
from app.interview.analysis.similarity_analyzer import SimilarityAnalyzer

logger = logging.getLogger(__name__)


class ElementAnalyzer:
    """
    Analyzes and categorizes user inputs for the ACV laddering model.
    Identifies attributes, consequences, values, and irrelevant content.
    """

    # Minimum character length for meaningful responses per category
    MIN_RESPONSE_LENGTH = 10

    # Maximum character length for summaries
    MAX_SUMMARY_LENGTH = 50

    # Storage for detected causal relationships
    causal_relationships = []
    
    # Template name constants
    TEMPLATE_IDEA_CHECK = "idea_check"
    TEMPLATE_NODE_TYPE_ANALYSIS = "node_type_analysis"

    @classmethod
    def _build_context_from_tree(cls, interview_tree: Optional['Tree'],
                                 effective_active_node: Optional['node'] = None,
                                 last_question: str = None) -> Dict[str, str]:
        """
        Creates optimized context information from the interview tree,
        automatically excluding irrelevant nodes.

        Args:
            interview_tree: Current interview tree
            effective_active_node: Optional - effective active node (if different from actual active)
            last_question: Optional - last asked question

        Returns:
            Dictionary with context information
        """
        active_node_info = ""

        if not interview_tree:
            return {
                "interview": "",
                "active_node_info": "",
                "last_question": last_question or ""
            }

        # Determine the active node to use
        if effective_active_node:
            # Use explicitly provided effective active node
            active_node = effective_active_node
        elif interview_tree.active:
            # Automatic determination: If active node is irrelevant, use parent
            active_node = interview_tree.active
            if active_node.get_label() == NodeLabel.IRRELEVANT_ANSWER:
                logger.debug(
                    f"Active node is IRRELEVANT (ID: {active_node.id}) - using parent")

                # Get parent of irrelevant node
                parents = active_node.get_parents()
                if parents:
                    active_node = parents[0]  # Use first parent
                    logger.debug(
                        f"Using parent node for context: {active_node.id} - {active_node.get_label().value}")
                else:
                    # Fallback: If no parent, use root or set to None
                    if interview_tree.get_tree_root():
                        active_node = interview_tree.get_tree_root()
                        logger.debug(
                            f"No parent found, using root: {active_node.id} - {active_node.get_label().value}")
                    else:
                        active_node = None
                        logger.debug("No parent or root found")
        else:
            active_node = None

        if not active_node:
            return {
                "interview": "",
                "active_node_info": "",
                "last_question": last_question or ""
            }

        # Enhanced active_node_info with context
        active_node_info = f"{active_node.get_label().value}: {active_node.get_conclusion()}"

        # Optimized path building with newest parent nodes, but without irrelevant nodes
        path_nodes = TreeUtils.build_optimized_path_excluding_irrelevant(
            interview_tree, active_node)

        # Filter out AUTO-generated nodes
        from app.interview.interview_tree.node_utils import NodeUtils
        filtered_path_nodes = []
        for node_obj in path_nodes:
            conclusion = node_obj.get_conclusion() or ""
            if not NodeUtils.is_auto_generated(conclusion):
                filtered_path_nodes.append(node_obj)

        # Format path with hierarchical indentations
        if filtered_path_nodes:
            # Reverse so hierarchy goes from root down
            reversed_path = list(reversed(filtered_path_nodes))

            # Formatted path entries with hierarchy indicators
            formatted_path = []
            for i, node_obj in enumerate(reversed_path):
                prefix = "└─" * i  # Hierarchy indicator
                entry = f"{prefix}{node_obj.get_label().value}: {node_obj.get_conclusion()}"
                formatted_path.append(entry)

            interview_context = "\n".join(formatted_path)
        else:
            interview_context = ""

        return {
            "interview": interview_context,
            "active_node_info": active_node_info,
            "last_question": last_question or ""
        }

    @classmethod
    async def check_idea(cls, message: str, client: Any, model: str,
                         topic: str = None, stimulus: str = None,
                         last_question: str = None) -> Tuple[bool, str, bool]:
        """
        Specifically checks if a user message contains a relevant IDEA (concrete application of the stimulus).
 
        Args:
            message: User message to analyze
            client: LLM client
            model: Model to use
            topic: Optional interview topic
            stimulus: Optional interview stimulus
            last_question: Optional last question asked
            
        Returns:
            Tuple of (is_idea, summary, is_relevant)
        """
        from app.llm.client import LlmClient
        
        logger.info(f"Check_idea called with message: '{message[:50]}...'")
        
        # Prepare template variables
        template_vars = {
            "topic": topic or 'not specified',
            "stimulus": stimulus or 'not specified',
            "message": message,
            "last_question": last_question or ''
        }
        
        # Use LLM client
        llm_client = LlmClient(client, model)
        
        # JSON schema for expected response
        json_schema = {
            "type": "object",
            "properties": {
                "is_idea": {"type": "boolean"},
                "summary": {"type": "string"},
                "is_relevant": {"type": "boolean"},
                "explanation": {"type": "string"}
            },
            "required": ["is_idea", "summary", "is_relevant", "explanation"]
        }
        
        # Use class variable for template name
        system_prompt = render_template(cls.TEMPLATE_IDEA_CHECK, **template_vars)
        
        try:
            # Prepare messages for LLM request
            messages = [{"role": "system", "content": system_prompt}]
            
            # Use standardized structured output method with optimal parameters for Groq
            raw_response = await llm_client.query_with_structured_output(
                messages=messages,
                schema=json_schema,
                temperature=0.2  # Lower temperature for more consistent analysis
            )
            
            # Parse the response
            import json
            from app.llm.utils import clean_json_response
            cleaned_json = clean_json_response(raw_response)
            parsed_data = json.loads(cleaned_json)
            
            # Extract results
            is_idea = parsed_data.get("is_idea", False)
            summary = parsed_data.get("summary", "")
            is_relevant = parsed_data.get("is_relevant", False)
            
            # Log the results
            if is_idea:
                logger.info(f"IDEA detected: '{summary}'")
            elif is_relevant:
                logger.info(f"Relevant but not an IDEA: '{summary}'")
            else:
                logger.info(f"IRRELEVANT response: '{summary}'")
                
            return (is_idea, summary, is_relevant)
            
        except Exception as e:
            logger.exception(f"Error in idea check: {e}")
            return (False, f"Error: {str(e)}", False)
    
    @classmethod
    async def judge_multi(cls, message: str, client: Any, model: str,
                        topic: str = None, stimulus: str = None, 
                        interview_tree: Optional['Tree'] = None, 
                        last_question: str = None) -> List[Tuple[NodeLabel, str, str, bool]]:
        """
        Analyzes a user message and identifies all ACV elements contained within.
        
        Args:
            message: User message to analyze
            client: LLM client
            model: Model to use
            topic: Optional interview topic
            stimulus: Optional interview stimulus
            interview_tree: Optional interview tree for context
            last_question: Optional last question asked
            
        Returns:
            Tuple of (elements_list, causal_relationships)
            where elements_list is a list of (NodeLabel, summary, text_segment, is_new_element)
        """
        from app.llm.client import LlmClient
        
        logger.info(f"Judge_multi called with message: '{message[:50]}...'")
        
        # Determine active node and label (for context check)
        active_node = None
        active_label = None
        active_node_label_str = "UNKNOWN"  # Default value
        effective_active_node = None  # Node actually used for prompting
        
        if interview_tree and interview_tree.active:
            active_node = interview_tree.active
            active_label = active_node.get_label()
            
            # If active node is irrelevant, use parent
            if active_label == NodeLabel.IRRELEVANT_ANSWER:
                logger.debug(f"Active node is IRRELEVANT (ID: {active_node.id}) - using parent for prompting")
                
                # Get parent of irrelevant node
                latest_parent = active_node.get_latest_parent()
                if latest_parent:
                    effective_active_node = latest_parent  # Use parent with highest ID
                    active_label = effective_active_node.get_label()
                    active_node_label_str = active_label.value if active_label else "UNKNOWN"
                    logger.debug(f"Using parent node for prompting: {effective_active_node.id} - {active_label.value}")
                else:
                    # Fallback: If no parent, use root or set to None
                    if interview_tree.get_tree_root():
                        effective_active_node = interview_tree.get_tree_root()
                        active_label = effective_active_node.get_label()
                        active_node_label_str = active_label.value if active_label else "UNKNOWN"
                        logger.debug(f"No parent found, using root: {effective_active_node.id} - {active_label.value}")
                    else:
                        effective_active_node = None
                        active_node_label_str = "UNKNOWN"
                        logger.debug(f"No parent or root found")
            else:
                # Normal case: Active node is not irrelevant
                effective_active_node = active_node
                active_node_label_str = active_label.value if active_label else "UNKNOWN"
        
        # Build context from tree
        context_info = cls._build_context_from_tree(
            interview_tree, 
            effective_active_node,
            last_question
        )
        
        # Create analysis prompt from template store
        template_vars = {
            "topic": topic or 'not specified',
            "stimulus": stimulus or 'not specified',
            "interview": context_info["interview"],
            "active_node_info": context_info["active_node_info"],
            "active_node_label": active_node_label_str, 
            "message": message,
            "last_question": context_info["last_question"]
        }
        
        # Use LLM client
        llm_client = LlmClient(client, model)
        
        # Define JSON schema for expected response
        json_schema = {
            "type": "object",
            "properties": {
                "contains_multiple_elements": {"type": "boolean"},
                "elements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": ["ATTRIBUTE", "CONSEQUENCE", "VALUE", "IRRELEVANT"]},
                            "summary": {"type": "string"},
                            "text_segment": {"type": "string"},
                            "is_new_element": {"type": "boolean"}
                        },
                        "required": ["category", "summary", "text_segment", "is_new_element"]
                    }
                },
                "causal_relationships": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_element_index": {"type": "integer"},
                            "target_element_index": {"type": "integer"},
                            "relationship_type": {"type": "string", "enum": ["A→C", "C→C", "C→V"]},
                            "explanation": {"type": "string"}
                        },
                        "required": ["source_element_index", "target_element_index", "relationship_type"]
                    }
                }
            },
            "required": ["contains_multiple_elements", "elements"]
        }
        
        # Use class variable for template name
        system_prompt = render_template(cls.TEMPLATE_NODE_TYPE_ANALYSIS, **template_vars)
        
        try:
            # Prepare messages for LLM request
            messages = [{"role": "system", "content": system_prompt}]
            
            # Use the standardized structured output method for all providers
            raw_response = await llm_client.query_with_structured_output(
                messages=messages,
                schema=json_schema,
                temperature=0.2,  # Lower temperature for more consistent analysis
            )
            
            # Parse response
            import json
            from app.llm.utils import clean_json_response
            cleaned_json = clean_json_response(raw_response)
            parsed_data = json.loads(cleaned_json)
            
            # Process LLM response with helper method
            effective_active_label = effective_active_node.get_label() if effective_active_node else None
            effective_active_conclusion = effective_active_node.get_conclusion() if effective_active_node else ""
            
            result_elements = cls._process_llm_analysis_response(
                parsed_data, message, effective_active_label, effective_active_conclusion
            )
            
            return result_elements, cls.causal_relationships
            
        except Exception as e:
            logger.exception(f"Error in multi-element analysis: {e}")
            return [], []


    @classmethod
    def _process_llm_analysis_response(cls, parsed_data: dict, message: str, 
                                      active_label: Optional[NodeLabel] = None, 
                                      active_conclusion: str = "") -> List[Tuple[NodeLabel, str, str, bool]]:
        """
        Processes parsed JSON response from LLM and extracts elements and causal relationships.
        
        Args:
            parsed_data: Parsed JSON data from LLM response
            message: Original user message
            active_label: Label of active node (for context checks)
            active_conclusion: Summary of active node
            
        Returns:
            List of tuples [(NodeLabel, summary, text_segment, is_new_element), ...]
        """
        # Extract elements
        elements_data = parsed_data.get("elements", [])
        result_elements = []
        
        # Storage for recognized elements (for later relationship mapping)
        recognized_elements = []
        
        # After parsing elements, check if they're new or repetitions
        for elem in elements_data:
            if not isinstance(elem, dict):
                continue
                
            category = elem.get("category", "")
            if not category:
                continue
            
            # If IRRELEVANT, create IRRELEVANT_ANSWER element
            if category == "IRRELEVANT":
                logger.info(f"Message identified as irrelevant: {elem.get('summary', 'No reason')}")
                node_label = NodeLabel.IRRELEVANT_ANSWER
                # For irrelevant answers, is_new is always True
                is_new = True
                summary = elem.get("summary", "").strip()
            elif category == "ATTRIBUTE":
                node_label = NodeLabel.ATTRIBUTE
                is_new = elem.get("is_new_element", True)
                summary = elem.get("summary", "").strip()
            elif category == "CONSEQUENCE":
                # Check if consequence is in context of active consequence
                if active_label == NodeLabel.CONSEQUENCE:
                    # Extract summary
                    consequence_summary = elem.get("summary", "").strip()
                    
                    # Consequence is relevant to active consequence -> process normally
                    node_label = NodeLabel.CONSEQUENCE
                    is_new = elem.get("is_new_element", True)
                    summary = consequence_summary
                    logger.info(f"Consequence '{summary}' is always relevant to active consequence '{active_conclusion}'")
                else:
                    # Normal case: No active consequence
                    node_label = NodeLabel.CONSEQUENCE
                    is_new = elem.get("is_new_element", True)
                    summary = elem.get("summary", "").strip()
            elif category == "VALUE":
                node_label = NodeLabel.VALUE
                is_new = elem.get("is_new_element", True)
                summary = elem.get("summary", "").strip()
            else:
                logger.warning(f"Unknown category: {category}")
                continue
            
            text_segment = elem.get("text_segment", message).strip()
            
            # For IRRELEVANT_ANSWER also accept shorter summaries
            min_length = 3 if node_label == NodeLabel.IRRELEVANT_ANSWER else cls.MIN_RESPONSE_LENGTH
            
            if summary and len(summary) >= min_length:
                # Shorten summary if needed
                if len(summary) > cls.MAX_SUMMARY_LENGTH:
                    summary = summary[:cls.MAX_SUMMARY_LENGTH-3] + "..."
                
                element_tuple = (node_label, summary, text_segment, is_new)
                result_elements.append(element_tuple)
                recognized_elements.append({
                    "index": len(recognized_elements),
                    "label": node_label,
                    "summary": summary,
                    "tuple": element_tuple
                })
        
        # Extract causal relationships
        causal_relationships = parsed_data.get("causal_relationships", [])
        
        # Process causal relationships
        if causal_relationships:
            cls._process_causal_relationships(causal_relationships, recognized_elements)
        
        # Log output for recognized elements
        element_count = len(result_elements)
        if element_count > 0:
            logger.info(f"Multiple elements detected: {element_count}")
            for i, (label, summary, _, is_new) in enumerate(result_elements):
                new_flag = "" if is_new else " (Repetition)"
                logger.info(f"Element {i+1}: {label.value} - {summary}{new_flag}")
        else:
            logger.info("No elements detected!")
        
        return result_elements

    @classmethod
    def _process_causal_relationships(cls, causal_relationships: List[dict],
                                      recognized_elements: List[dict]) -> None:
        """
        Processes detected causal relationships between elements.

        Args:
            causal_relationships: List of detected causal relationships
            recognized_elements: List of detected elements with their indices
        """
        # Store detected relationships in class
        cls.causal_relationships = []

        for rel in causal_relationships:
            source_idx = rel.get("source_element_index")
            target_idx = rel.get("target_element_index")
            rel_type = rel.get("relationship_type")
            explanation = rel.get("explanation", "")

            # Check if indices are valid
            if source_idx is None or target_idx is None or source_idx == target_idx:
                logger.warning(f"Invalid relationship found: {rel}")
                continue

            if source_idx < 0 or source_idx >= len(recognized_elements) or \
               target_idx < 0 or target_idx >= len(recognized_elements):
                logger.warning(f"Invalid index in relationship: {rel}")
                continue

            # Get involved elements
            source_element = recognized_elements[source_idx]
            target_element = recognized_elements[target_idx]

            # Validate relationship types based on element types
            source_label = source_element["label"]
            target_label = target_element["label"]

            valid_relation = False
            if rel_type == "A→C" and source_label == NodeLabel.ATTRIBUTE and target_label == NodeLabel.CONSEQUENCE:
                valid_relation = True
            elif rel_type == "C→C" and source_label == NodeLabel.CONSEQUENCE and target_label == NodeLabel.CONSEQUENCE:
                valid_relation = True
            elif rel_type == "C→V" and source_label == NodeLabel.CONSEQUENCE and target_label == NodeLabel.VALUE:
                valid_relation = True

            if valid_relation:
                # Store relationship
                relationship = {
                    "source_element": source_element["tuple"],
                    "target_element": target_element["tuple"],
                    "relationship_type": rel_type,
                    "explanation": explanation
                }
                cls.causal_relationships.append(relationship)

                # Debug output for detected relationship
                source_summary = source_element["summary"]
                target_summary = target_element["summary"]
                logger.debug(
                    f"Causal relationship found ({rel_type}): '{source_summary}' → '{target_summary}'")
                if explanation:
                    logger.debug(f"Explanation: {explanation}")
            else:
                logger.warning(
                    f"Invalid relationship type {rel_type} for {source_label.value} → {target_label.value}")
