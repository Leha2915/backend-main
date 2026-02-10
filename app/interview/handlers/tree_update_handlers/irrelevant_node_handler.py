"""
Handler for irrelevant nodes in the interview tree.
Manages the creation, transformation and stacking of irrelevant nodes.
"""

import logging
from typing import Optional, List

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree import Tree as InterviewTree
from app.interview.handlers.tree_update_handlers.base_tree_handler import BaseTreeHandler

logger = logging.getLogger(__name__)


class IrrelevantNodeHandler(BaseTreeHandler):
    """
    Handles all operations related to irrelevant nodes in the interview tree.
    """

    def transform_irrelevant_node(self, irrelevant_node: Node, label: NodeLabel, summary: str,
                                  is_first_message: bool, interaction_id: Optional[int] = None,
                                  parent_node: Optional[Node] = None) -> Optional[Node]:
        """
        Transforms an irrelevant node into a regular node with the specified label.
        """
        if irrelevant_node.get_label() != NodeLabel.IRRELEVANT_ANSWER:
            logger.warning(
                f"Attempted transformation of non-irrelevant node: {irrelevant_node.id}")
            return None

        logger.info(
            f"Transforming irrelevant node {irrelevant_node.id} to {label.value}")

        # Debug: Output of the original trace elements in the irrelevant node
        logger.debug(
            f"Original trace elements in irrelevant node {irrelevant_node.id}:")
        if hasattr(irrelevant_node, 'trace') and irrelevant_node.trace:
            for i, trace_elem in enumerate(irrelevant_node.trace):
                logger.debug(
                    f"Trace element {i+1}: Interaction={trace_elem.interaction_id}, Node-Ref={trace_elem.node.id if trace_elem.node else 'None'}")
        else:
            logger.debug(
                f"No trace elements found in irrelevant node {irrelevant_node.id}")

        # Save trace elements of the irrelevant node
        trace_elements = irrelevant_node.trace.copy() if hasattr(
            irrelevant_node, 'trace') else []

        # Add new trace element for the current interaction, if available
        if interaction_id:
            from app.interview.models.trace_explanation_element import TraceExplanationElement
            trace_elem = TraceExplanationElement(interaction_id, None)
            trace_elements.append(trace_elem)
            logger.info(
                f"New trace element with interaction {interaction_id} added for transformation")

        logger.debug(
            f"Total {len(trace_elements)} trace elements prepared for transfer")

        # Save the parent nodes of the irrelevant node
        original_parent_nodes = irrelevant_node.get_parents().copy()

        # Save the originally active node
        original_active = self.tree.active

        # Use the passed parent_node if available
        if parent_node:
            logger.info(
                f"Using explicit parent node for transformation: {parent_node.id} - {parent_node.get_label().value}")

            # Create the new node directly under the specified parent node
            self.tree.active = parent_node
            new_node = self.tree.add_child(
                label=label,
                trace=[],  # Empty list, as we add trace elements manually
                conclusion=summary
            )
            self.tree.active = original_active  # Restore active node

            # Transfer trace elements to the new node and update node references
            logger.info(
                f"Transferring {len(trace_elements)} trace elements and updating node references")
            for trace_elem in trace_elements:
                if hasattr(new_node, 'trace'):
                    new_node.trace.append(trace_elem)
                else:
                    new_node.trace = [trace_elem]
                # Update the node reference to the new node
                trace_elem.node = new_node

            logger.info(
                f"Irrelevant node {irrelevant_node.id} successfully transformed to {label.value} node {new_node.id} under explicit parent node {parent_node.id}")
            return new_node

        # If no explicit parent_node was specified:
        # Special case: If a parent node is a STIMULUS, transform directly to IDEA
        for parent in original_parent_nodes:
            if parent.get_label() == NodeLabel.STIMULUS:
                logger.info(
                    f"Parent node is STIMULUS: Transforming directly to IDEA under stimulus (ID: {parent.id})")

                # Override the label with IDEA
                transformed_label = NodeLabel.IDEA

                # Check if an IDEA node already exists under this STIMULUS
                existing_idea_nodes = [node for node in parent.get_children()
                                       if node.get_label() == NodeLabel.IDEA]

                if existing_idea_nodes:
                    # Use the first existing IDEA node
                    existing_node = existing_idea_nodes[0]
                    logger.info(
                        f"Existing IDEA node (ID: {existing_node.id}) found under stimulus, combining summaries")

                    # Combine the existing summary with the new one
                    current_summary = existing_node.get_conclusion()
                    combined_summary = f"{current_summary}, {summary}"
                    existing_node.set_conclusion(combined_summary)

                    # Transfer trace elements to the existing node
                    for trace_elem in trace_elements:
                        if hasattr(existing_node, 'trace'):
                            existing_node.trace.append(trace_elem)
                        else:
                            existing_node.trace = [trace_elem]
                        # Update the node reference to the existing node
                        trace_elem.node = existing_node

                    logger.info(
                        f"Irrelevant node {irrelevant_node.id} successfully transformed to existing IDEA node {existing_node.id} under STIMULUS")
                    return existing_node
                else:
                    # When creating the new node, use base handler method
                    new_node = self.create_and_add_node(
                        parent_node=parent,
                        label=transformed_label,
                        summary=summary,
                        is_first_message=is_first_message,
                    )

                    # Transfer trace elements to the new node and update node references
                    for trace_elem in trace_elements:
                        if hasattr(new_node, 'trace'):
                            if trace_elem not in new_node.trace:  # Avoid duplicates
                                new_node.trace.append(trace_elem)
                        else:
                            new_node.trace = [trace_elem]
                        # Update the node reference to the new node
                        trace_elem.node = new_node

                    logger.info(
                        f"Irrelevant node {irrelevant_node.id} successfully transformed to new IDEA node {new_node.id} under STIMULUS")
                    return new_node

        # Standard case: Regular transformation with existing logic
        # Find the appropriate parent node for the new node
        target_parent_node = None
        if original_parent_nodes:
            # Use the first parent node as starting point for the search
            original_parent = original_parent_nodes[0]

            target_parent_node = self.find_parent_node(
                label, is_first_message, original_parent)

            if not target_parent_node:
                target_parent_node = self.create_intermediate_nodes(
                    label, original_parent)

            # Fallback to the first parent node
            if not target_parent_node:
                target_parent_node = original_parent
        else:
            # Fallback to root, if no parents were found
            target_parent_node = self.tree.get_tree_root()

        # Create the new node and insert it at the right position
        self.tree.active = target_parent_node
        new_node = self.tree.add_child(
            label=label,
            trace=[],  # Pass empty list, as we add the trace elements manually
            conclusion=summary
        )

        # Update the node references in the copied trace elements
        for trace_elem in trace_elements:
            if hasattr(new_node, 'trace'):
                new_node.trace.append(trace_elem)
            else:
                new_node.trace = [trace_elem]
            # Update the node reference to the new node
            trace_elem.node = new_node

        # Restore active node
        self.tree.active = original_active

        logger.info(
            f"Irrelevant node {irrelevant_node.id} successfully transformed to {label.value} node {new_node.id}, but not yet removed")
        return new_node

    def handle_irrelevant_answer(self, summary: str, is_first_message: bool, interaction_id: Optional[int] = None) -> Optional[Node]:
        """
        Handles irrelevant answers by creating irrelevant nodes.
        """
        logger.info(f"Handling irrelevant answer: '{summary}'")

        # Check if the active node is already an IRRELEVANT_ANSWER dummy node
        active_node = self.tree.active
        if active_node and active_node.get_label() == NodeLabel.IRRELEVANT_ANSWER:
            # Stack further irrelevant answers with interaction ID
            # when stacking
            return self.stack_irrelevant_answer(active_node, summary, interaction_id)

        # Create new dummy node
        parent_node = active_node if active_node else self.tree.get_tree_root()

        # Mark as dummy node with special prefix
        dummy_summary = f"DUMMY-{self.get_irrelevant_counter()}: {summary}"

        # Use base handler method to create node
        dummy_node = self.create_and_add_node(
            parent_node, NodeLabel.IRRELEVANT_ANSWER,
            dummy_summary, is_first_message, interaction_id)

        if dummy_node:
            logger.info(
                f"Dummy node created: ID={dummy_node.id}, Summary='{dummy_summary}'")
            if interaction_id:
                logger.info(
                    f"Dummy node linked with interaction {interaction_id}")

        return dummy_node

    def stack_irrelevant_answer(self, existing_dummy: Node, new_summary: str, interaction_id: Optional[int] = None) -> Node:
        """
        Stacks another irrelevant answer onto an existing dummy node.
        """
        # Extract current counter from the conclusion
        current_conclusion = existing_dummy.get_conclusion() or ""
        current_counter = self.extract_counter_from_conclusion(
            current_conclusion)
        new_counter = current_counter + 1

        # Stack the new answer (keep the original + new)
        if "| STACK:" in current_conclusion:
            # There are already stacked answers
            stacked_conclusion = f"{current_conclusion} | STACK-{new_counter}: {new_summary}"
        else:
            # First stacked answer
            stacked_conclusion = f"{current_conclusion} | STACK-{new_counter}: {new_summary}"

        # Shorten if too long, but keep counter info
        if len(stacked_conclusion) > 200:
            # Keep only the most important parts: Original + last stack + counter
            original_part = current_conclusion.split(
                " | STACK:")[0]  # Original part
            new_part = f"STACK-{new_counter}: {new_summary[:50]}..."
            stacked_conclusion = f"{original_part} | {new_part} (Total: {new_counter})"

        existing_dummy.set_conclusion(stacked_conclusion)

        # Add a new trace element for the current interaction
        if interaction_id:
            from app.interview.models.trace_explanation_element import TraceExplanationElement
            trace_elem = TraceExplanationElement(
                interaction_id, existing_dummy)
            if hasattr(existing_dummy, 'trace'):
                existing_dummy.trace.append(trace_elem)
            else:
                existing_dummy.trace = [trace_elem]
            logger.info(
                f"Stacking dummy node linked with interaction {interaction_id}")

        logger.info(
            f"Irrelevant answer #{new_counter} stacked on dummy node {existing_dummy.id}")
        logger.info(f"New conclusion: '{stacked_conclusion}'")

        return existing_dummy

    def extract_counter_from_conclusion(self, conclusion: str) -> int:
        """
        Extracts the counter from a dummy node conclusion.
        """
        try:
            # Check for "Total: X" format (in shortened conclusions)
            if "(Total:" in conclusion:
                total_part = conclusion.split(
                    "(Total:")[-1].strip().rstrip(")")
                return int(total_part)

            # Count STACK entries
            if "STACK-" in conclusion:
                stack_entries = conclusion.count("STACK-")
                return stack_entries  # Counter = number of STACK entries

            # Fallback: Check DUMMY-X format
            if "DUMMY-" in conclusion:
                dummy_part = conclusion.split("DUMMY-")[1].split(":")[0]
                return int(dummy_part)

        except (ValueError, IndexError):
            pass

        return 1  # Default counter

    def get_irrelevant_counter(self) -> int:
        """
        Returns the next dummy node number.
        """
        # Count existing IRRELEVANT_ANSWER nodes
        irrelevant_nodes = self.tree.get_nodes_by_label(
            NodeLabel.IRRELEVANT_ANSWER)
        return len(irrelevant_nodes) + 1
