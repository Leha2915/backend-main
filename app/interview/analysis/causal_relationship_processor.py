"""
Processor for causal relationships in the interview analysis.
Handles the analysis and processing of causal relationships between elements.
"""

import logging
from typing import Dict, List, Set, Tuple, Any, Optional

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree import Tree as InterviewTree

logger = logging.getLogger(__name__)


class CausalRelationshipProcessor:
    """
    Processes causal relationships between elements in the interview analysis.
    Handles the identification of complete chains, filtering, and relationship mapping.
    """

    def __init__(self, tree: InterviewTree):
        """
        Initialize the processor with the interview tree.

        Args:
            tree: The interview tree to work with
        """
        self.tree = tree

    def build_element_mappings(self, elements: List[Tuple[NodeLabel, str, bool]],
                               causal_relationships: List[Dict[str, Any]]):
        """
        Build mappings for elements and relationships.

        Args:
            elements: List of element tuples (NodeLabel, summary, is_new)
            causal_relationships: List of causal relationships

        Returns:
            Tuple of (elements_map, elements_in_relationships, source_elements,
                     target_elements, end_nodes_keys, relationship_map)
        """
        # Mapping of (label, summary) -> element tuple
        elements_map = {}

        # Create map for quick access to elements
        for elem in elements:
            element_label, element_summary, is_new_element = elem
            elements_map[(element_label, element_summary)] = elem

        # Identify all elements that appear in causal relationships
        elements_in_relationships = set()
        source_elements = set()  # Elements that appear as source
        target_elements = set()  # Elements that appear as target

        for rel in causal_relationships:
            source_elem = rel.get("source_element")
            target_elem = rel.get("target_element")

            if source_elem and len(source_elem) >= 2:
                # (Label, Summary)
                source_key = (source_elem[0], source_elem[1])
                elements_in_relationships.add(source_key)
                source_elements.add(source_key)

            if target_elem and len(target_elem) >= 2:
                # (Label, Summary)
                target_key = (target_elem[0], target_elem[1])
                elements_in_relationships.add(target_key)
                target_elements.add(target_key)

        # Determine end nodes: Target elements that never appear as source
        end_nodes_keys = target_elements - source_elements

        # Group causal relationships by Source element
        relationship_map = {}
        for rel in causal_relationships:
            source_elem = rel.get("source_element")
            target_elem = rel.get("target_element")

            if not source_elem or not target_elem or len(source_elem) < 2 or len(target_elem) < 2:
                continue

            source_key = (source_elem[0], source_elem[1])  # (Label, Summary)
            target_key = (target_elem[0], target_elem[1])  # (Label, Summary)

            if source_key not in relationship_map:
                relationship_map[source_key] = []

            relationship_map[source_key].append(target_key)

        return (elements_map, elements_in_relationships, source_elements,
                target_elements, end_nodes_keys, relationship_map)

    def identify_values_in_complete_acv_chains(self, elements, causal_relationships):
        """
        Identifies Values that are part of a complete ACV chain (A→C→...→V).
        Handles both direct A→C→V chains and chains with multiple consequences.
    
        Args:
            elements: List of detected elements
            causal_relationships: List of detected causal relationships
    
        Returns:
            Set of Value tuples (label, summary) that are part of a complete ACV chain
        """
        values_in_acv_chains = set()
        
        # Create maps of elements by type for quick access
        attribute_elements = {
            (NodeLabel.ATTRIBUTE, elem[1]) for elem in elements if elem[0] == NodeLabel.ATTRIBUTE}
        value_elements = {
            (NodeLabel.VALUE, elem[1]) for elem in elements if elem[0] == NodeLabel.VALUE}
        
        # Build a complete relationship graph
        relationship_graph = {}
        
        for rel in causal_relationships:
            source_elem = rel.get("source_element")
            target_elem = rel.get("target_element")
            
            if not source_elem or not target_elem or len(source_elem) < 2 or len(target_elem) < 2:
                continue
                
            source_key = (source_elem[0], source_elem[1])
            target_key = (target_elem[0], target_elem[1])
            
            if source_key not in relationship_graph:
                relationship_graph[source_key] = []
            relationship_graph[source_key].append(target_key)
        
        # Helper function for recursive path tracing
        def is_connected_to_attribute(node_key, visited=None):
            if visited is None:
                visited = set()
                
            # Avoid cycles
            if node_key in visited:
                return False
                
            visited.add(node_key)
            
            # Check all incoming relationships
            for source_key, targets in relationship_graph.items():
                if node_key in targets:
                    # If source is an Attribute, we found a path
                    if source_key[0] == NodeLabel.ATTRIBUTE:
                        logger.info(f"Found attribute connection: {source_key[1]} → ... → {node_key[1]}")
                        return True
                        
                    # If source is something else, check recursively
                    if is_connected_to_attribute(source_key, visited):
                        return True
                        
            return False
        
        # For each Value element, check if it's part of any ACV chain
        for value_elem in value_elements:
            # Check direct connections first (optimization)
            direct_connection = False
            for source_key, targets in relationship_graph.items():
                if value_elem in targets and source_key[0] == NodeLabel.CONSEQUENCE:
                    # Check if this Consequence is connected to an Attribute (directly or indirectly)
                    if is_connected_to_attribute(source_key):
                        logger.info(f"Complete ACV chain found ending with: {source_key[1]} → {value_elem[1]}")
                        values_in_acv_chains.add(value_elem)
                        direct_connection = True
                        break
            
            if direct_connection:
                continue
                
            # Otherwise check if the Value is indirectly connected to an Attribute
            if is_connected_to_attribute(value_elem):
                logger.info(f"Complex ACV chain found ending with value: {value_elem[1]}")
                values_in_acv_chains.add(value_elem)
        
        return values_in_acv_chains

    def filter_acv_chains(self, elements, causal_relationships):
        """
        Filters out Values that are part of complete ACV chains and their relationships.

        Args:
            elements: List of detected elements
            causal_relationships: List of detected causal relationships

        Returns:
            Tuple of (filtered_elements, filtered_relationships)
        """
        # Identify Values that are part of complete ACV chains
        values_in_acv_chains = self.identify_values_in_complete_acv_chains(
            elements, causal_relationships)

        if not values_in_acv_chains:
            return elements, causal_relationships

        logger.info(
            f"Found: {len(values_in_acv_chains)} Values in complete ACV chains")

        # Filter out Values that are part of a complete ACV chain
        filtered_elements = []
        for elem in elements:
            label, summary, is_new = elem
            if label == NodeLabel.VALUE and (label, summary) in values_in_acv_chains:
                logger.info(
                    f"Removing Value from complete ACV chain: '{summary}'")
            else:
                filtered_elements.append(elem)

        # Also filter out corresponding C→V relationships from causal_relationships
        filtered_relationships = []
        for rel in causal_relationships:
            source_elem = rel.get("source_element")
            target_elem = rel.get("target_element")

            # Check if this is a C→V relationship to be removed
            if (source_elem and target_elem and
                len(source_elem) >= 2 and len(target_elem) >= 2 and
                    source_elem[0] == NodeLabel.CONSEQUENCE and target_elem[0] == NodeLabel.VALUE):

                target_key = (target_elem[0], target_elem[1])
                if target_key in values_in_acv_chains:
                    logger.info(
                        f"Removing C→V relationship: '{source_elem[1]}' → '{target_elem[1]}'")
                    continue  # Don't add this relationship to filtered list

            # Keep all other relationships
            filtered_relationships.append(rel)

        logger.info(
            f"After ACV chain filtering: {len(filtered_elements)} elements and {len(filtered_relationships)} relationships remain")

        return filtered_elements, filtered_relationships

    def is_connected_to_value(self, consequence_key, causal_relationships, visited=None):
        """
        Recursively checks if a Consequence is connected to a Value.

        Args:
            consequence_key: The key of the consequence to check
            causal_relationships: List of causal relationships
            visited: Set of already visited keys

        Returns:
            True if connected to a Value, False otherwise
        """
        if visited is None:
            visited = set()

        # Avoid infinite loops
        if consequence_key in visited:
            return False

        visited.add(consequence_key)

        # Check all causal relationships
        for rel in causal_relationships:
            source = rel.get("source_element")
            target = rel.get("target_element")

            if not source or not target or len(source) < 2 or len(target) < 2:
                continue

            source_key = (source[0], source[1])
            target_key = (target[0], target[1])

            # Case 1: This Consequence leads directly to a Value
            if source_key == consequence_key and target[0] == NodeLabel.VALUE:
                return True

            # Case 2: This Consequence leads to another Consequence
            if source_key == consequence_key and target[0] == NodeLabel.CONSEQUENCE:
                # Recursively check if the target Consequence is connected to a Value
                if self.is_connected_to_value(target_key, causal_relationships, visited):
                    return True

        return False

    def filter_consequences_without_values(self, elements, causal_relationships):
        """
        Filters out Consequences that are not connected to Values.

        Args:
            elements: List of detected elements
            causal_relationships: List of detected causal relationships

        Returns:
            Filtered list of elements
        """
        if not self.tree or not self.tree.active or self.tree.active.get_label() != NodeLabel.CONSEQUENCE:
            return elements

        # Check if both Consequences and Values were detected
        has_consequences = any(
            element[0] == NodeLabel.CONSEQUENCE for element in elements)
        has_values = any(element[0] == NodeLabel.VALUE for element in elements)

        if not (has_consequences and has_values):
            return elements

        logger.info(
            "Active node is C and both C and V were detected - prioritizing Values")

        # Identify Consequences with direct or indirect causal relationships to Values
        connected_consequences = set()

        # First collect all direct C→V relationships
        for rel in causal_relationships:
            source_elem = rel.get("source_element")
            target_elem = rel.get("target_element")

            # Direct relationship from C→V
            if (source_elem and target_elem and
                len(source_elem) >= 2 and len(target_elem) >= 2 and
                    source_elem[0] == NodeLabel.CONSEQUENCE and target_elem[0] == NodeLabel.VALUE):
                # Mark C as connected
                connected_consequences.add(
                    (source_elem[0], source_elem[1]))

        # Now check all Consequences (that aren't directly connected) for indirect connections
        for elem in elements:
            label, summary, is_new = elem
            if label == NodeLabel.CONSEQUENCE and (label, summary) not in connected_consequences:
                if self.is_connected_to_value((label, summary), causal_relationships):
                    logger.info(
                        f"Indirect Value relationship found for: {summary}")
                    connected_consequences.add((label, summary))

        # Filter elements: Keep Values and (directly or indirectly) connected Consequences
        filtered_elements = []
        for elem in elements:
            label, summary, is_new = elem
            if label == NodeLabel.VALUE or (label == NodeLabel.CONSEQUENCE and (label, summary) in connected_consequences):
                filtered_elements.append(elem)
            elif label != NodeLabel.CONSEQUENCE:
                # Keep Attributes and other non-Consequences
                filtered_elements.append(elem)
            else:
                logger.info(
                    f"Removing unconnected Consequence: '{summary}' (no direct or indirect relationship to Values)")

        logger.info(
            f"After Value prioritization: {len(filtered_elements)} elements remain")

        return filtered_elements

    async def process_source_element_special_cases(self, source_key, target_keys, elements_map,
                                                 node_creator, processed_nodes, all_processed_nodes,
                                                 end_nodes_keys, final_nodes, client=None, model=None,
                                                 topic=None, stimulus=None, interaction_id=None):
        """
        Processes special cases for source elements that aren't marked as new.
    
        Args:
            source_key: The key of the source element
            target_keys: The keys of the target elements
            elements_map: Mapping of element keys to elements
            node_creator: Function to create or reuse nodes
            processed_nodes: Map of already processed nodes
            all_processed_nodes: List of all processed nodes
            end_nodes_keys: Set of keys for end nodes
            final_nodes: List of nodes to return
    
        Returns:
            True if special case was handled, False otherwise
        """
        source_label, source_summary = source_key
    
        # Check if the element is new
        source_elem = elements_map.get(source_key)
        # source_elem[2] is is_new_element
        if not source_elem or not source_elem[2]:
            # Check if we should perform special handling despite "not new"
            active_node = self.tree.active if self.tree else None
    
            if not active_node:
                return False
    
            active_label = active_node.get_label()
    
            # Case 1: Active node is A and source element is A or C
            if active_label == NodeLabel.ATTRIBUTE and (source_label == NodeLabel.ATTRIBUTE or source_label == NodeLabel.CONSEQUENCE):
                logger.info(
                    f"Source element ignored, but target elements without parent nodes processed: {source_label.value} - '{source_summary}'")
    
                # Process all target elements without the parent node
                for target_key in target_keys:
                    target_label, target_summary = target_key
    
                    # Check if target element is new
                    target_elem = elements_map.get(target_key)
                    # target_elem[2] is is_new_element
                    if not target_elem or not target_elem[2]:
                        logger.info(
                            f"Skipping target element (Case 1): {target_label.value} - '{target_summary}' - not new or not found")
                        continue
    
                    logger.info(
                        f"Processing target element without parent (Case 1): {target_label.value} - '{target_summary}'")
                    # Without parent_node! ADDED AWAIT HERE ↓
                    target_node = await node_creator(target_label, target_summary,
                                               client=client, model=model,
                                               topic=topic, stimulus=stimulus,
                                               interaction_id=interaction_id)
                    if target_node:
                        processed_nodes[target_key] = target_node
                        all_processed_nodes.append((target_key, target_node))
    
                        # Only add end nodes to final_nodes list
                        if target_key in end_nodes_keys:
                            final_nodes.append(target_node)
    
                return True  # Skip source element
    
            # Case 2: Active node is C and source element is C or V
            elif active_label == NodeLabel.CONSEQUENCE and (source_label == NodeLabel.CONSEQUENCE or source_label == NodeLabel.VALUE):
                logger.info(
                    f"Source element ignored, but target elements without parent nodes processed: {source_label.value} - '{source_summary}'")
    
                # Process all target elements without the parent node
                for target_key in target_keys:
                    target_label, target_summary = target_key
    
                    # Check if target element is new
                    target_elem = elements_map.get(target_key)
                    # target_elem[2] is is_new_element
                    if not target_elem or not target_elem[2]:
                        logger.info(
                            f"Skipping target element (Case 2): {target_label.value} - '{target_summary}' - not new or not found")
                        continue
    
                    logger.info(
                        f"Processing target element without parent (Case 2): {target_label.value} - '{target_summary}'")
                    # Without parent_node! ADDED AWAIT HERE ↓
                    target_node = await node_creator(target_label, target_summary,
                                               client=client, model=model,
                                               topic=topic, stimulus=stimulus,
                                               interaction_id=interaction_id)
                    if target_node:
                        processed_nodes[target_key] = target_node
                        all_processed_nodes.append((target_key, target_node))
    
                        # Only add end nodes to final_nodes list
                        if target_key in end_nodes_keys:
                            final_nodes.append(target_node)
    
                return True  # Skip source element
    
            # Case 3: Active node is C and source element is A - skip as before
            elif active_label == NodeLabel.CONSEQUENCE and source_label == NodeLabel.ATTRIBUTE:
                logger.info(
                    f"New consequences found in different context (active: C, source: A)")
    
                # List all associated target elements being ignored
                for target_key in target_keys:
                    target_label, target_summary = target_key
                    logger.info(
                        f"   ↳ Ignoring dependent element: {target_label.value} - '{target_summary}'")
    
                return True  # Skip source element
    
        # Default case: No special handling required
        return False
