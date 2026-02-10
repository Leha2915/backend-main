"""
Similarity analyzer module for comparing and evaluating node similarities.
Provides functions for contextual and direct content similarity assessment.
"""

import re
import logging
from typing import List, Dict, Any, Optional

from app.llm.template_store import render_template
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.node_utils import NodeUtils
from app.llm.client import LlmClient
from app.interview.interview_tree.tree_utils import TreeUtils

logger = logging.getLogger(__name__)


class SimilarityAnalyzer:
    """
    Provides methods for comparing and evaluating similarities between nodes.
    Supports both content-based and context-aware similarity checks.
    """
    
    # Template name constant
    TEMPLATE_NODE_SIMILARITY_CHECK = "node_similarity_check"

    @classmethod
    async def check_contextual_similarity(cls, new_node: 'Node', merge_candidates: List['Node'],
                                         tree_obj: 'Tree', client: Any,
                                         model: str, topic: str, stimulus: str) -> List[Dict[str, Any]]:
        """
        Performs a context-based similarity check with multiple candidates in parallel.
        Uses LLM to determine if nodes are similar enough to merge based on their context paths.
        
        Args:
            new_node: New node to check
            merge_candidates: List of candidate nodes for merging
            tree_obj: Interview tree
            client: LLM client
            model: Model to use
            topic: Interview topic
            stimulus: Interview stimulus
        
        Returns:
            List of dictionaries with similarity check results
        """
        # Ensure new node exists
        if not new_node:
            return [{"candidate_node": candidate,
                    "should_merge": False,
                     "confidence_score": 100,
                     "explanation": "The new node is None"}
                    for candidate in merge_candidates]
        
        # Extract path for new node with optimized path building
        new_node_path = TreeUtils.build_optimized_path_excluding_irrelevant(
            tree_obj, new_node)
        
        # Filter out AUTO-generated nodes
        new_node_path_filtered = []
        for n in new_node_path:
            conclusion = n.get_conclusion() or ""
            if not NodeUtils.is_auto_generated(conclusion):
                new_node_path_filtered.append(n)
        
        # Formatted path for new node
        new_node_path_formatted = cls._format_node_path(new_node_path_filtered)
        
        # Format candidates with their paths
        candidates_formatted = ""
        for i, candidate in enumerate(merge_candidates):
            if not candidate:
                continue
        
            # Extract path for candidate
            candidate_path = TreeUtils.build_optimized_path_excluding_irrelevant(
                tree_obj, candidate)
        
            # Filter out AUTO-generated nodes
            candidate_path_filtered = []
            for n in candidate_path:
                conclusion = n.get_conclusion() or ""
                if not NodeUtils.is_auto_generated(conclusion):
                    candidate_path_filtered.append(n)
        
            # Formatted path for candidate
            candidate_path_formatted = cls._format_node_path(
                candidate_path_filtered)
        
            # Add candidate entry
            candidates_formatted += f"CANDIDATE {i}:\n"
            candidates_formatted += f"- Summary: \"{candidate.get_conclusion()}\"\n"
            candidates_formatted += f"- Full context path (from element to root):\n{candidate_path_formatted}\n\n"
        
        # Prepare template variables
        template_vars = {
            "node_type": new_node.get_label().value,
            "new_node_summary": new_node.get_conclusion(),
            "new_node_path": new_node_path_formatted,
            "candidates_formatted": candidates_formatted,
            "topic": topic or "not specified",
            "stimulus": stimulus or "not specified",
            "num_candidates": len(merge_candidates),
            # Safe calculation with minimum 0
            "num_candidates_minus_one": max(0, len(merge_candidates) - 1)
        }
        
        # Use LLM client
        llm_client = LlmClient(client, model)
        
        # JSON schema for expected response
        json_schema = {
            "type": "object",
            "properties": {
                "similarity_results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "candidate_id": {"type": "integer"},
                            "should_merge": {"type": "boolean"},
                            "explanation": {"type": "string"},
                            "confidence_score": {"type": "integer", "minimum": 0, "maximum": 100}
                        },
                        "required": ["candidate_id", "should_merge", "explanation", "confidence_score"]
                    }
                }
            },
            "required": ["similarity_results"]
        }
        
        # Use class variable for template name
        system_prompt = render_template(
            cls.TEMPLATE_NODE_SIMILARITY_CHECK, **template_vars)
        
        try:
            # Prepare messages for LLM request
            messages = [{"role": "system", "content": system_prompt}]
            
            # Use standardized structured output method
            raw_response = await llm_client.query_with_structured_output(
                messages=messages,
                schema=json_schema,
                temperature=0.1,  # Very low temperature for consistent similarity judgments
            )
            
            # Parse the response
            import json
            from app.llm.utils import clean_json_response
            cleaned_json = clean_json_response(raw_response)
            parsed_data = json.loads(cleaned_json)
            
            similarity_results = parsed_data.get("similarity_results", [])
        
            # Connect results with actual candidate nodes
            final_results = []
            for result in similarity_results:
                candidate_id = result.get("candidate_id", -1)
                if 0 <= candidate_id < len(merge_candidates):
                    candidate_node = merge_candidates[candidate_id]
                    final_results.append({
                        "candidate_node": candidate_node,
                        "should_merge": result.get("should_merge", False),
                        "explanation": result.get("explanation", ""),
                        "confidence_score": result.get("confidence_score", 0)
                    })
        
            logger.info(
                f"Similarity check yielded {len(final_results)} results")
            return final_results
        
        except Exception as e:
            logger.exception(f"Error in context-based similarity check: {e}")
            return [{
                "candidate_node": candidate,
                "should_merge": False,
                "confidence_score": 0,
                "explanation": f"Error: {str(e)}"
            } for candidate in merge_candidates]

    @classmethod
    def _format_node_path(cls, path_nodes):
        """
        Formats a path of nodes for similarity checking.
        Creates a hierarchical representation with indentation.

        Args:
            path_nodes: List of nodes in the path

        Returns:
            Formatted string representation of the path
        """
        # Reverse so hierarchy goes from root down
        reversed_path = list(reversed(path_nodes))

        # Formatted path entries with hierarchy indicators
        formatted = []
        for i, n in enumerate(reversed_path):
            prefix = "└─" * i  # Hierarchy indicator
            entry = f"{prefix}{n.get_label().value}({n.id}): {n.get_conclusion()}"
            formatted.append(entry)

        return "\n".join(formatted)

    @classmethod
    def is_similar_element(cls, element1: str, element2: str, element_type: NodeLabel = None) -> bool:
        """
        Checks if two elements are similar in content, based on various similarity metrics.
        The method uses multiple strategies from simple to more complex comparisons.

        Args:
            element1: First element to compare
            element2: Second element to compare
            element_type: Optional - Node type for context-specific thresholds

        Returns:
            True if elements are considered similar, otherwise False
        """
        if not element1 or not element2:
            return False

        # Normalize strings
        element1 = element1.lower().strip()
        element2 = element2.lower().strip()

        # 1. Exact match (fastest test)
        if element1 == element2:
            return True

        # 2. Substring check for shorter texts
        if len(element1) <= 30 or len(element2) <= 30:
            # If one is a substring of the other, they're similar
            if element1 in element2 or element2 in element1:
                return True

        # 3. Word set comparison with improved logic
        # Words with at least 3 letters
        words1 = set(re.findall(r'\b\w{3,}\b', element1))
        words2 = set(re.findall(r'\b\w{3,}\b', element2))

        # Count common words
        common_words = words1.intersection(words2)

        # Adjust thresholds based on element type
        word_match_threshold = 0.35  # Default threshold
        min_common_words = 2

        if element_type:
            # Specific thresholds by element type
            if element_type == NodeLabel.VALUE:
                # Values can be more abstract, use lower threshold
                word_match_threshold = 0.25
                min_common_words = 1
            elif element_type == NodeLabel.CONSEQUENCE:
                # Consequences are more concrete, medium threshold
                word_match_threshold = 0.30
                min_common_words = 2
            elif element_type == NodeLabel.ATTRIBUTE:
                # Attributes are very concrete, higher threshold
                word_match_threshold = 0.35
                min_common_words = 2

        # Calculate Jaccard similarity
        if words1 or words2:  # Avoid division by zero
            jaccard = len(common_words) / len(words1.union(words2))

            # Adjust Jaccard threshold based on text length
            if len(words1) <= 3 and len(words2) <= 3:
                # For very short texts: One common word can be relevant
                if len(common_words) >= min_common_words or jaccard >= (word_match_threshold - 0.1):
                    return True
            elif len(words1) <= 6 and len(words2) <= 6:
                # For medium-length texts: Expect more match
                if len(common_words) >= min_common_words or jaccard >= word_match_threshold:
                    return True
            else:
                # For longer texts: Require even higher match
                if len(common_words) >= (min_common_words + 1) or jaccard >= (word_match_threshold + 0.05):
                    return True

        # No similarity found
        return False
