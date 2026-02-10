"""
Message Processing Manager for the Interview Engine.
Manages the processing of user messages and their analysis.
"""

import logging
from typing import List, Any, Optional, Tuple, Dict, Set

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree import Tree as InterviewTree
from app.interview.analysis.element_analyzer import ElementAnalyzer
from app.interview.analysis.causal_relationship_processor import CausalRelationshipProcessor
from app.interview.handlers.tree_update_handlers.chat_tree_update_handler import TreeUpdateManager

logger = logging.getLogger(__name__)


class MessageProcessingManager:
    """
    Manages the processing and analysis of user messages.
    """

    def __init__(self, tree: InterviewTree):
        self.tree = tree
        self.tree_updater = TreeUpdateManager(tree) if tree else None
        self.relationship_processor = CausalRelationshipProcessor(tree) if tree else None
        # List for all nodes affected by the last message
        self.all_nodes_last_message = []
        # Temporary collection for nodes created in the current operation
        self._all_nodes_this_message = []

    async def process_message(self, message: str, client: Any, model: str,
                              is_first_content_message: bool, last_question: str,
                              topic: str, stimulus: str, interaction_id: Optional[int] = None) -> List[Node]:
        """
        Processes a user message and returns created nodes.
        
        Args:
            message: The user message to process
            client: LLM client
            model: LLM model to use
            is_first_content_message: Whether this is the first content message
            last_question: The last question asked
            topic: The current topic
            stimulus: The current stimulus
            interaction_id: Optional ID of the interaction
            
        Returns:
            List of created nodes
        """
        try:
            logger.debug(f"Analyzing user message: '{message}'")
            # Clear temporary node collection at the beginning
            self._all_nodes_this_message = []

            if is_first_content_message:
                return await self._process_first_content_message(message, client, model, last_question, topic, stimulus, interaction_id)
            else:
                return await self._process_regular_message(message, client, model, last_question, topic, stimulus, interaction_id)

        except Exception as e:
            logger.warning(f"Error during message analysis: {e}")
            return []

    async def _process_first_content_message(self, message: str, client: Any = None, model: str = None, 
                                           last_question: str = None, topic: str = None, 
                                           stimulus: str = None, interaction_id: Optional[int] = None) -> List[Node]:
        """
        Processes the first content message and checks for relevance and IDEA quality.
        
        Args:
            message: The user message to process
            client: LLM client
            model: LLM model to use
            last_question: The last question asked
            topic: The current topic
            stimulus: The current stimulus
            interaction_id: Optional ID of the interaction
            
        Returns:
            List of created nodes
        """
        # IDEA check with specialized method
        logger.debug("Checking first message for IDEA quality...")
        is_idea, summary, is_relevant = await ElementAnalyzer.check_idea(
            message=message,
            client=client,
            model=model,
            topic=topic,
            stimulus=stimulus,
            last_question=last_question
        )

        # Determine label and summary based on analysis results
        label, summary = self._determine_first_message_label_and_summary(
            is_idea, is_relevant, summary, message)

        if not self.tree_updater:
            return []

        # Create node with appropriate label
        new_node = self.tree_updater.update_tree_with_analysis(
            label, summary, is_first_message=True, interaction_id=interaction_id
        )

        if new_node:
            # Save newly created nodes in the list for all affected nodes
            self._all_nodes_this_message.append(new_node)
            logger.info(
                f"{label.value} node created with ID {new_node.id}: '{new_node.get_conclusion()}'")
            return [new_node]

        return []
        
    def _determine_first_message_label_and_summary(self, is_idea: bool, is_relevant: bool, 
                                                 summary: str, message: str) -> Tuple[NodeLabel, str]:
        """
        Determines the label and summary for the first message.
        
        Args:
            is_idea: Whether the message contains an idea
            is_relevant: Whether the message is relevant
            summary: The summary from the analyzer
            message: The original message
            
        Returns:
            Tuple of (label, summary)
        """
        if not is_relevant:
            logger.info("Message identified as irrelevant - marking as IRRELEVANT_ANSWER")
            label = NodeLabel.IRRELEVANT_ANSWER
            
            # Use summary from IDEA check or create fallback
            if not summary or len(summary) < 5:
                summary = f"Irrelevant: {message[:20]}..." if len(
                    message) > 20 else f"Irrelevant: {message}"
                    
        elif is_idea:
            logger.info(f"Concrete IDEA detected: '{summary}' - creating IDEA node")
            label = NodeLabel.IDEA
            # Use LLM-generated summary for better consistency
            if not summary or len(summary) < 5:
                summary = message[:30] + "..." if len(message) > 30 else message
                
        else:
            # Relevant but not a concrete IDEA - still classify as IDEA for flow
            logger.info("Relevant answer but not concrete IDEA - classifying as IDEA for interview flow")
            label = NodeLabel.IDEA
            # Use summary from IDEA check or create a new one
            if not summary or len(summary) < 5:
                summary = message[:30] + "..." if len(message) > 30 else message
            logger.debug(f"Used summary: '{summary}'")
            
        return label, summary

    async def _process_regular_message(self, message: str, client: Any, model: str, 
                                     last_question: str = None, topic: str = None, 
                                     stimulus: str = None, interaction_id: Optional[int] = None) -> List[Node]:
        """
        Processes regular messages with full analysis.
        
        Args:
            message: The user message to process
            client: LLM client
            model: LLM model to use
            last_question: The last question asked
            topic: The current topic
            stimulus: The current stimulus
            interaction_id: Optional ID of the interaction
            
        Returns:
            List of created nodes
        """
        # Extract multiple elements
        raw_elements, causal_relationships = await ElementAnalyzer.judge_multi(
            message=message,
            client=client,
            model=model,
            topic=topic,
            stimulus=stimulus,
            interview_tree=self.tree,
            last_question=last_question
        )

        # Convert 4-element tuples to 3-element tuples by removing text_segment
        elements = [(label, summary, is_new)
                    for label, summary, _, is_new in raw_elements]
        logger.info(
            f"ElementAnalyzer.judge_multi returned {len(elements)} elements and {len(causal_relationships)} relationships")

        # Check if we have elements to process
        if not elements:
            logger.info("Answer ignored - no elements detected")
            return []
        
        # Check for irrelevant elements - if found, only process the first irrelevant element
        irrelevant_elements = [element for element in elements if element[0] == NodeLabel.IRRELEVANT_ANSWER]
        if irrelevant_elements:
            # Keep only the first irrelevant element
            first_irrelevant = irrelevant_elements[0]
            elements = [first_irrelevant]
            # Clear relationships since we're only processing one element
            causal_relationships = []
            logger.info(f"Irrelevant element detected - processing only the first irrelevant element: '{first_irrelevant[1]}'")
            
        # Check for complete ACV chains
        elements, causal_relationships = self._filter_acv_chains_if_needed(elements, causal_relationships)
        
        # Filter consequences without value relationships
        elements = self._filter_consequences_if_needed(elements, causal_relationships)

        # Process all elements and relationships
        return await self._process_elements_and_relationships(
            elements, causal_relationships, client=client, model=model, 
            topic=topic, stimulus=stimulus, interaction_id=interaction_id)
            
    def _filter_acv_chains_if_needed(self, elements, causal_relationships):
        """
        Filters ACV chains if needed.
        
        Args:
            elements: List of elements
            causal_relationships: List of causal relationships
            
        Returns:
            Tuple of (filtered_elements, filtered_relationships)
        """
        # Check if complete ACV chains were detected
        has_attributes = any(element[0] == NodeLabel.ATTRIBUTE for element in elements)
        has_consequences = any(element[0] == NodeLabel.CONSEQUENCE for element in elements)
        has_values = any(element[0] == NodeLabel.VALUE for element in elements)
        
        if has_attributes and has_consequences and has_values:
            logger.info("A, C and V elements detected - checking for complete ACV chains...")
            return self.relationship_processor.filter_acv_chains(elements, causal_relationships)
            
        return elements, causal_relationships
        
    def _filter_consequences_if_needed(self, elements, causal_relationships):
        """
        Filters consequences if needed.
        
        Args:
            elements: List of elements
            causal_relationships: List of causal relationships
            
        Returns:
            Filtered list of elements
        """
        return self.relationship_processor.filter_consequences_without_values(elements, causal_relationships)

    async def _process_elements_and_relationships(self, elements: List[Tuple[NodeLabel, str, bool]],
                                               causal_relationships: List[dict], client=None, 
                                               model=None, topic=None, stimulus=None, 
                                               interaction_id=None) -> List[Node]:
        """
        Unified processing of elements and their causal relationships.
        
        Args:
            elements: List of element tuples (NodeLabel, summary, is_new)
            causal_relationships: List of causal relationships
            client: LLM client
            model: LLM model to use
            topic: The current topic
            stimulus: The current stimulus
            interaction_id: Optional ID of the interaction
            
        Returns:
            List of created nodes
        """
        # Build mappings for elements and relationships
        (elements_map, elements_in_relationships, source_elements,
         target_elements, end_nodes_keys, relationship_map) = (
            self.relationship_processor.build_element_mappings(elements, causal_relationships)
        )
        
        # Lists for tracking nodes
        all_processed_nodes = []  # All nodes processed
        final_nodes = []          # Nodes to return
        processed_nodes = {}      # Map of processed nodes by key
        
        # 1. Process independent elements
        await self._process_independent_elements(
            elements, elements_in_relationships, all_processed_nodes, 
            final_nodes, client, model, topic, stimulus, interaction_id
        )
        
        # 2. Process elements with causal relationships
        await self._process_relationship_elements(
            relationship_map, elements_map, processed_nodes,
            all_processed_nodes, end_nodes_keys, final_nodes,
            client, model, topic, stimulus, interaction_id
        )
            
        # 3. Sort final nodes for queue
        final_nodes = self._sort_final_nodes(final_nodes)
        
        # Store all nodes affected in current step
        self.all_nodes_last_message = list(self._all_nodes_this_message)
        logger.info(
            f"all_nodes_last_message after processing: {[getattr(n, 'id', None) for n in self.all_nodes_last_message]}")
            
        return final_nodes
        
    async def _process_independent_elements(self, elements, elements_in_relationships,
                                         all_processed_nodes, final_nodes,
                                         client, model, topic, stimulus, interaction_id):
        """
        Process elements that don't appear in any causal relationships.
        
        Args:
            elements: List of elements
            elements_in_relationships: Set of elements that appear in relationships
            all_processed_nodes: List to collect all processed nodes
            final_nodes: List of nodes to return
            client, model, topic, stimulus, interaction_id: Standard parameters
        """
        for idx, (element_label, element_summary, is_new_element) in enumerate(elements):
            element_key = (element_label, element_summary)
            
            if element_key not in elements_in_relationships and is_new_element:
                logger.info(
                    f"Processing independent element {idx+1}/{len(elements)}: {element_label.value} - '{element_summary}'")
                    
                created_node = await self._create_or_reuse_node(
                    element_label, element_summary, 
                    client=client, model=model, topic=topic, 
                    stimulus=stimulus, interaction_id=interaction_id
                )
                
                if created_node:
                    all_processed_nodes.append((element_key, created_node))
                    # Always include independent elements in final_nodes
                    final_nodes.append(created_node)
                    
    async def _process_relationship_elements(self, relationship_map, elements_map, processed_nodes,
                                          all_processed_nodes, end_nodes_keys, final_nodes,
                                          client, model, topic, stimulus, interaction_id):
        """
        Process elements that appear in causal relationships.
        
        Args:
            relationship_map: Map of source keys to lists of target keys
            elements_map: Map of element keys to elements
            processed_nodes: Map to collect processed nodes
            all_processed_nodes: List to collect all processed nodes
            end_nodes_keys: Set of keys for end nodes
            final_nodes: List of nodes to return
            client, model, topic, stimulus, interaction_id: Standard parameters
        """
        for source_key, target_keys in relationship_map.items():
            source_label, source_summary = source_key
            
            # Handle special cases for non-new source elements
            # Modified to use an async callback function correctly
            special_case_handled = await self.relationship_processor.process_source_element_special_cases(
                source_key, target_keys, elements_map, 
                # Pass the async function references, not a lambda that calls it
                self._create_or_reuse_node,
                processed_nodes, all_processed_nodes, end_nodes_keys, final_nodes,
                client=client, model=model, topic=topic, 
                stimulus=stimulus, interaction_id=interaction_id
            )
            
            if special_case_handled:
                continue
                
            # Standard case: Process source element and its targets
            await self._process_standard_relationship(
                source_key, source_label, source_summary, target_keys, 
                elements_map, processed_nodes, all_processed_nodes, 
                end_nodes_keys, final_nodes,
                client, model, topic, stimulus, interaction_id
            )
            
    async def _process_standard_relationship(self, source_key, source_label, source_summary,
                                          target_keys, elements_map, processed_nodes,
                                          all_processed_nodes, end_nodes_keys, final_nodes,
                                          client, model, topic, stimulus, interaction_id):
        """
        Process a standard source-target relationship.
        
        Args:
            source_key, source_label, source_summary: Source element info
            target_keys: List of target keys
            elements_map: Map of element keys to elements
            processed_nodes: Map of processed nodes
            all_processed_nodes, end_nodes_keys, final_nodes: Collection tracking
            client, model, topic, stimulus, interaction_id: Standard parameters
        """
        # Create/find the source node
        logger.info(
            f"Processing source element from causal relationship: {source_label.value} - '{source_summary}'")
            
        source_node, node_reused = await self._get_or_create_source_node(
            source_key, source_label, source_summary,
            processed_nodes, all_processed_nodes, end_nodes_keys, final_nodes,
            client, model, topic, stimulus, interaction_id
        )
        
        if not source_node:
            logger.warning(
                f"Could not create or reuse source node: {source_label.value} - '{source_summary}'")
            return
            
        # Process all target nodes with source node as parent
        await self._process_target_nodes(
            source_node, target_keys, elements_map, processed_nodes,
            all_processed_nodes, end_nodes_keys, final_nodes,
            client, model, topic, stimulus, interaction_id
        )
        
    async def _get_or_create_source_node(self, source_key, source_label, source_summary,
                                      processed_nodes, all_processed_nodes, end_nodes_keys, final_nodes,
                                      client, model, topic, stimulus, interaction_id):
        """
        Get an existing source node or create a new one.
        
        Args:
            source_key, source_label, source_summary: Source element info
            processed_nodes, all_processed_nodes, end_nodes_keys, final_nodes: Collection tracking
            client, model, topic, stimulus, interaction_id: Standard parameters
            
        Returns:
            Tuple of (source_node, node_reused)
        """
        if source_key in processed_nodes:
            source_node = processed_nodes[source_key]
            logger.info(f"Using already created source node: {source_node.id}")
            return source_node, True
            
        # Create new node
        source_node = await self._create_or_reuse_node(
            source_label, source_summary,
            client=client, model=model, topic=topic, 
            stimulus=stimulus, interaction_id=interaction_id
        )
        
        if source_node:
            processed_nodes[source_key] = source_node
            all_processed_nodes.append((source_key, source_node))
            
            # Add source element only if it's also an end node (unlikely)
            if source_key in end_nodes_keys:
                final_nodes.append(source_node)
                
            return source_node, True
            
        # Check if node exists in another branch and can be reused
        existing_node, _ = await self.tree_updater.find_existing_similar_node(
            source_label, source_summary,
            client=client, model=model, topic=topic, stimulus=stimulus
        )
        
        if existing_node:
            logger.info(f"Source element found in another branch (ID: {existing_node.id})")
            return existing_node, True
            
        return None, False
        
    async def _process_target_nodes(self, source_node, target_keys, elements_map, processed_nodes,
                                 all_processed_nodes, end_nodes_keys, final_nodes,
                                 client, model, topic, stimulus, interaction_id):
        """
        Process all target nodes with the given source node as parent.
        
        Args:
            source_node: The parent node
            target_keys: List of target keys
            elements_map: Map of element keys to elements
            processed_nodes: Map of processed nodes
            all_processed_nodes, end_nodes_keys, final_nodes: Collection tracking
            client, model, topic, stimulus, interaction_id: Standard parameters
        """
        for target_key in target_keys:
            target_label, target_summary = target_key
            
            # Check if target element is new
            target_elem = elements_map.get(target_key)
            if not target_elem or not target_elem[2]:  # target_elem[2] is is_new_element
                logger.info(
                    f"Skipping target element: {target_label.value} - '{target_summary}' - not new or not found")
                continue
                
            logger.info(
                f"Processing target element from causal relationship: {target_label.value} - '{target_summary}'")
                
            if target_key in processed_nodes:
                await self._add_existing_target_node(
                    target_key, target_label, processed_nodes,
                    source_node, all_processed_nodes, end_nodes_keys, final_nodes
                )
            else:
                await self._create_new_target_node(
                    target_key, target_label, target_summary, source_node,
                    processed_nodes, all_processed_nodes, end_nodes_keys, final_nodes,
                    client, model, topic, stimulus, interaction_id
                )
                
    async def _add_existing_target_node(self, target_key, target_label, processed_nodes,
                                     source_node, all_processed_nodes, end_nodes_keys, final_nodes):
        """
        Add an existing target node as a child of the source node.
        
        Args:
            target_key: The key of the target element
            target_label: The label of the target element
            processed_nodes: Map of processed nodes
            source_node: The parent node
            all_processed_nodes, end_nodes_keys, final_nodes: Collection tracking
        """
        target_node = processed_nodes[target_key]
        logger.info(f"Adding already created target node as child: {target_node.id}")
        
        # Add existing node as child
        added_node = self.tree_updater.add_existing_node_as_child(
            target_node, target_label, parent_node=source_node)
            
        if added_node:
            all_processed_nodes.append((target_key, added_node))
            
            # Only add end nodes to final_nodes list
            if target_key in end_nodes_keys:
                final_nodes.append(added_node)
                
    async def _create_new_target_node(self, target_key, target_label, target_summary,
                                   source_node, processed_nodes, all_processed_nodes, 
                                   end_nodes_keys, final_nodes,
                                   client, model, topic, stimulus, interaction_id):
        """
        Create a new target node as a child of the source node.
        
        Args:
            target_key, target_label, target_summary: Target element info
            source_node: The parent node
            processed_nodes: Map of processed nodes
            all_processed_nodes, end_nodes_keys, final_nodes: Collection tracking
            client, model, topic, stimulus, interaction_id: Standard parameters
        """
        # Create new node directly with correct parent node
        target_node = await self._create_or_reuse_node(
            target_label, target_summary, 
            parent_node=source_node,
            client=client, model=model, topic=topic, 
            stimulus=stimulus, interaction_id=interaction_id
        )
        
        if target_node:
            processed_nodes[target_key] = target_node
            all_processed_nodes.append((target_key, target_node))
            
            # Only add end nodes to final_nodes list
            if target_key in end_nodes_keys:
                final_nodes.append(target_node)

    def _sort_final_nodes(self, final_nodes):
        """
        Sort final nodes for the queue.
        Consequences are reversed to ensure correct processing order.
        
        Args:
            final_nodes: List of nodes to sort
            
        Returns:
            Sorted list of nodes
        """
        consequence_nodes = []
        non_consequence_nodes = []
        
        for node_obj in final_nodes:
            if node_obj.get_label() == NodeLabel.CONSEQUENCE:
                consequence_nodes.append(node_obj)
            else:
                non_consequence_nodes.append(node_obj)
                
        # Reverse Consequences so the last one is inserted first in queue
        consequence_nodes.reverse()
        
        # Debug output
        logger.info(
            f"Total final nodes: {len(consequence_nodes) + len(non_consequence_nodes)} "
            f"(Consequences: {len(consequence_nodes)}, Others: {len(non_consequence_nodes)})")
            
        return consequence_nodes + non_consequence_nodes

    async def _create_or_reuse_node(self, label: NodeLabel, summary: str, 
                                 parent_node: Optional[Node] = None, 
                                 client=None, model=None, topic=None, 
                                 stimulus=None, interaction_id=None) -> Optional[Node]:
        """
        Creates a new node or reuses an existing one.
        
        Args:
            label: The label of the node to create
            summary: The summary of the node
            parent_node: Optional parent node for the new node
            client, model, topic, stimulus, interaction_id: Standard parameters
            
        Returns:
            The created or reused node, or None on error
        """
        if not self.tree_updater:
            return None
            
        # Special handling for IRRELEVANT_ANSWER - these should always be stacked
        if label == NodeLabel.IRRELEVANT_ANSWER:
            logger.info(
                f"IRRELEVANT_ANSWER detected - using direct tree update logic for stacking")
            node = self.tree_updater.update_tree_with_analysis(
                label, summary, is_first_message=False, 
                parent_node=parent_node, interaction_id=interaction_id
            )
            
            if node:
                self._all_nodes_this_message.append(node)
            return node
            
        # Search for existing similar node for other label types
        existing_node, is_duplicate_to_ignore = await self.tree_updater.find_existing_similar_node(
            label, summary, client=client, model=model, topic=topic, stimulus=stimulus)
            
        # If it's a duplicate that should be ignored (under same parent node or cycle)
        if is_duplicate_to_ignore:
            logger.warning(
                f"Ignoring input completely: '{summary}' is a duplicate or would create a cycle")
            if existing_node:
                self._all_nodes_this_message.append(existing_node)
            return None
            
        if existing_node:
            return await self._reuse_existing_node(existing_node, label, parent_node)
        else:
            return await self._create_new_node(label, summary, parent_node, interaction_id)
            
    async def _reuse_existing_node(self, existing_node, label, parent_node):
        """
        Reuse an existing node.
        
        Args:
            existing_node: The existing node to reuse
            label: The label of the node
            parent_node: Optional parent node
            
        Returns:
            The reused node or None
        """
        logger.info(
            f"Using existing {label.value} node from another branch: '{existing_node.get_conclusion()}'")
        # Pass label to find semantic parent node
        added_node = self.tree_updater.add_existing_node_as_child(
            existing_node, label, parent_node)
        
        if added_node:
            self._all_nodes_this_message.append(added_node)
            return added_node
        else:
            logger.info(f"Node not added to queue (no new connection created)")
            self._all_nodes_this_message.append(existing_node)
            return None
            
    async def _create_new_node(self, label, summary, parent_node, interaction_id):
        """
        Create a new node.
        
        Args:
            label: The label of the node
            summary: The summary of the node
            parent_node: Optional parent node
            interaction_id: Optional interaction ID
            
        Returns:
            The created node or None
        """
        # Create new node
        node = self.tree_updater.update_tree_with_analysis(
            label, summary, is_first_message=False, 
            parent_node=parent_node, interaction_id=interaction_id
        )
        
        if node:
            self._all_nodes_this_message.append(node)
        return node