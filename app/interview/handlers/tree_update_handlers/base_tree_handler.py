"""
Base handler containing shared tree update functionality.
Prevents circular imports between tree update handlers.
"""

import logging
from typing import Optional, List, Dict, Any

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree import Tree as InterviewTree
from app.interview.interview_tree.tree_utils import TreeUtils
from app.interview.interview_tree.node_utils import NodeUtils

logger = logging.getLogger(__name__)


class BaseTreeHandler:
    """
    Base class containing shared tree manipulation methods.
    Used by TreeUpdateManager and specialized node handlers.
    """

    def __init__(self, tree: InterviewTree):
        self.tree = tree

    def find_parent_node(self, label: NodeLabel, is_first_message: bool, original_active_node: Node) -> Optional[Node]:
        """Finds the appropriate parent node for a new node."""
        logger.info(f"Searching parent node for {label.value} node")

        if is_first_message:
            # For the first message (IDEA): Find the STIMULUS node
            stimulus_nodes = self.tree.get_nodes_by_label(NodeLabel.STIMULUS)
            if stimulus_nodes:
                parent_node = original_active_node
                logger.info(
                    f"First message: Using STIMULUS as parent node (ID: {parent_node.id})")
                return parent_node
            else:
                logger.warning("No STIMULUS node found!")
                return None

        # For subsequent messages
        return self.find_parent_by_hierarchy(label, original_active_node)

    def find_parent_by_hierarchy(self, label: NodeLabel, original_active_node: Node) -> Optional[Node]:
        """Finds the parent node based on the ACV hierarchy."""
        # Read only, do not modify
        current_node = original_active_node
        active_label = current_node.get_label() if current_node else None

        logger.info(
            f"To be placed under: {current_node.id} - {active_label.value if active_label else 'None'}")

        # Check for direct hierarchical relationship
        if self.is_valid_hierarchy_match(active_label, label):
            parent_node = current_node
            logger.info(
                f"ACV hierarchy: {label.value} under {active_label.value} (ID: {parent_node.id})")
            return parent_node

        # Search for semantically matching parent node without changing active node
        return self.find_semantic_parent(label, original_active_node)

    def is_valid_hierarchy_match(self, active_label: Optional[NodeLabel], target_label: NodeLabel) -> bool:
        """Checks if there is a valid hierarchical relationship between two labels."""
        if not active_label or not target_label:
            return False

        valid_combinations = [
            (NodeLabel.IDEA, NodeLabel.ATTRIBUTE),
            (NodeLabel.ATTRIBUTE, NodeLabel.CONSEQUENCE),
            (NodeLabel.CONSEQUENCE, NodeLabel.VALUE),
            (NodeLabel.CONSEQUENCE, NodeLabel.CONSEQUENCE)
        ]

        return (active_label, target_label) in valid_combinations

    def find_semantic_parent(self, label: NodeLabel, original_active_node: Node) -> Optional[Node]:
        """Finds the semantically matching parent node."""
        logger.info(
            "No direct ACV hierarchy found, searching semantically matching parent node...")

        if label == NodeLabel.ATTRIBUTE:
            return self.find_idea_parent(original_active_node)
        elif label == NodeLabel.CONSEQUENCE:
            return self.find_attribute_or_consequence_parent(original_active_node)
        elif label == NodeLabel.VALUE:
            return self.find_consequence_parent(original_active_node)

        return None

    def find_stimulus_ancestor(self, node_obj: Optional[Node]) -> Optional[Node]:
        """
        Finds the stimulus ancestor of a given node.
        """
        if not node_obj:
            return None

        # If the node itself is a stimulus, return it
        if node_obj.get_label() == NodeLabel.STIMULUS:
            return node_obj

        # Otherwise traverse the tree upward
        path = self.tree.get_nodes_path_to_root(node_obj)
        for ancestor in path:
            if ancestor.get_label() == NodeLabel.STIMULUS:
                return ancestor

        return None

    def find_idea_parent(self, original_active_node: Node) -> Optional[Node]:
        """
        Finds an IDEA node as parent node for attributes, but only within
        the current stimulus context.
        """
        # Determine the current stimulus context
        current_stimulus = self.find_stimulus_ancestor(original_active_node)
        if not current_stimulus:
            # No current stimulus context found, fallback to global search
            idea_nodes = self.tree.get_nodes_by_label(NodeLabel.IDEA)
            if idea_nodes:
                parent_node = idea_nodes[-1]  # Take the newest IDEA
                logger.warning(
                    f"No stimulus context found, using newest IDEA: ID={parent_node.id}")
                return parent_node
            else:
                logger.warning("No IDEA nodes found, using current node")
                return original_active_node

        # Find all direct IDEA children of the current stimulus
        stimulus_ideas = [
            node_obj for node_obj in current_stimulus.get_children()
            if node_obj.get_label() == NodeLabel.IDEA
        ]

        if stimulus_ideas:
            # Take the newest IDEA under this stimulus
            parent_node = stimulus_ideas[-1]
            logger.info(
                f"Found: IDEA node ID={parent_node.id} under current stimulus {current_stimulus.id}")
            return parent_node
        else:
            logger.warning(
                f"No IDEA nodes under stimulus {current_stimulus.id}, using stimulus as parent node")
            return current_stimulus

    def find_attribute_or_consequence_parent(self, original_active_node: Node) -> Optional[Node]:
        """Finds an ATTRIBUTE node as parent node for Consequences."""
        # Read only, do not change
        current_node = original_active_node

        # If the current node is an attribute
        if current_node and current_node.get_label() == NodeLabel.ATTRIBUTE:
            logger.info(
                f"Candidate for Consequence: ATTRIBUTE node ID={current_node.id}")
            return current_node

        # If the current node is a consequence
        if current_node and current_node.get_label() == NodeLabel.CONSEQUENCE:
            logger.info(
                f"Candidate for Consequence: CONSEQUENCE node ID={current_node.id}")
            return current_node

        return None

    def find_consequence_parent(self, original_active_node: Node) -> Optional[Node]:
        """Finds a CONSEQUENCE node as parent node for Values."""
        # Read only, do not change
        current_node = original_active_node

        # If the current node is a consequence
        if current_node and current_node.get_label() == NodeLabel.CONSEQUENCE:
            logger.info(
                f"Candidate for Value: CONSEQUENCE node ID={current_node.id}")
            return current_node

        return None

    def create_intermediate_nodes(self, label: NodeLabel, original_active_node: Node) -> Optional[Node]:
        """Creates missing intermediate nodes for the ACV hierarchy."""
        logger.info("Creating missing intermediate nodes for ACV hierarchy...")

        if not original_active_node:
            return None

        active_label = original_active_node.get_label()
        # Temporary parent node, without changing self.tree.active
        temp_parent = original_active_node

        if label == NodeLabel.VALUE:
            if active_label == NodeLabel.ATTRIBUTE:
                return self.create_consequence_intermediate(temp_parent, original_active_node)
            elif active_label == NodeLabel.IDEA:
                return self.create_attribute_and_consequence_intermediate(temp_parent, original_active_node)
        elif label == NodeLabel.CONSEQUENCE:
            if active_label == NodeLabel.IDEA:
                return self.create_attribute_intermediate(temp_parent, original_active_node)

        return None

    def create_consequence_intermediate(self, parent_node: Node, original_active_node: Node) -> Optional[Node]:
        """Creates a CONSEQUENCE intermediate node."""
        logger.info("Creating CONSEQUENCE as intermediate node for VALUE")
        auto_label, auto_summary, _ = NodeUtils.create_auto_generated_node(
            NodeLabel.CONSEQUENCE)

        # Temporary active node for this operation
        temp_active = original_active_node
        self.tree.active = parent_node

        conseq_node = self.tree.add_child(
            label=auto_label,
            trace=[],
            conclusion=auto_summary
        )

        # Reset active node
        self.tree.active = temp_active

        logger.info(f"Created CONSEQUENCE node: {conseq_node.id}")
        return conseq_node

    def create_attribute_intermediate(self, parent_node: Node, original_active_node: Node) -> Optional[Node]:
        """Creates an ATTRIBUTE intermediate node."""
        logger.info("Creating ATTRIBUTE as intermediate node for CONSEQUENCE")
        auto_label, auto_summary, _ = NodeUtils.create_auto_generated_node(
            NodeLabel.ATTRIBUTE)

        # Temporary active node for this operation
        temp_active = original_active_node
        self.tree.active = parent_node

        attr_node = self.tree.add_child(
            label=auto_label,
            trace=[],
            conclusion=auto_summary
        )

        # Reset active node
        self.tree.active = temp_active

        logger.info(f"Created ATTRIBUTE node: {attr_node.id}")
        return attr_node

    def create_attribute_and_consequence_intermediate(self, parent_node: Node, original_active_node: Node) -> Optional[Node]:
        """Creates ATTRIBUTE and CONSEQUENCE intermediate nodes."""
        logger.info("Creating A and C as intermediate nodes for VALUE")

        # Temporary active node for this operation
        temp_active = original_active_node

        # Create attribute
        self.tree.active = parent_node
        auto_label_a, auto_summary_a, _ = NodeUtils.create_auto_generated_node(
            NodeLabel.ATTRIBUTE)
        attr_node = self.tree.add_child(
            label=auto_label_a,
            trace=[],
            conclusion=auto_summary_a
        )
        logger.info(f"Created ATTRIBUTE node: {attr_node.id}")

        # Create consequence
        self.tree.active = attr_node
        auto_label_c, auto_summary_c, _ = NodeUtils.create_auto_generated_node(
            NodeLabel.CONSEQUENCE)
        conseq_node = self.tree.add_child(
            label=auto_label_c,
            trace=[],
            conclusion=auto_summary_c
        )

        # Reset active node
        self.tree.active = temp_active

        logger.info(f"Created CONSEQUENCE node: {conseq_node.id}")
        return conseq_node

    def create_and_add_node(self, parent_node: Optional[Node], label: NodeLabel,
                            summary: str, is_first_message: bool, interaction_id: Optional[int] = None) -> Optional[Node]:
        """Creates and adds a new node to the tree."""

        # Save the originally active node
        original_active = self.tree.active

        # Create trace element with interaction ID
        trace_elements = []
        if interaction_id:
            from app.interview.models.trace_explanation_element import TraceExplanationElement
            trace_elem = TraceExplanationElement(
                interaction_id, None)  # Node will be set later
            trace_elements = [trace_elem]
            logger.info(
                f"Trace element with interaction {interaction_id} created")

        if not parent_node:
            logger.warning(
                "No matching parent node found, adding to current node")
            # No change to self.tree.active here, use the existing active node
            new_node = self.tree.add_child(
                label=label,
                trace=trace_elements,
                conclusion=summary
            )
        else:
            logger.info(
                f"Setting parent node: {parent_node.id} - {parent_node.get_label().value}")

            # Here it is safe to change the active node, as we are now actually
            # adding the new node
            temp_active = self.tree.active
            self.tree.active = parent_node

            # Add new node
            new_node = self.tree.add_child(
                label=label,
                trace=trace_elements,
                conclusion=summary
            )
            # Reset active node
            self.tree.active = temp_active

            if is_first_message:
                logger.info("IDEA node added as child of STIMULUS node")

        # Debug output
        if new_node and interaction_id and trace_elements:
            for trace_elem in trace_elements:
                trace_elem.node = new_node
            logger.info(
                f"Node {new_node.id} linked with interaction {interaction_id}")

        # Special case: Backward relationship ATTRIBUTE to CONSEQUENCE
        if original_active and new_node and original_active.get_label() == NodeLabel.CONSEQUENCE and label == NodeLabel.ATTRIBUTE:
            logger.info(
                f"Backward relationship detected: Consequence {original_active.id} → Attribute {new_node.id}")
            # Save the backward relationship in the consequence
            original_active.add_backwards_relation(new_node)

        # Special case: Backward relationship ATTRIBUTE to ATTRIBUTE
        if original_active and new_node and original_active.get_label() == NodeLabel.ATTRIBUTE and label == NodeLabel.ATTRIBUTE:
            logger.info(
                f"Backward relationship detected: Attribute {original_active.id} → Attribute {new_node.id}")
            # Save the backward relationship in the original attribute
            original_active.add_backwards_relation(new_node)

        return new_node
