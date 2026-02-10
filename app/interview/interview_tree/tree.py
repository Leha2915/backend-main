"""
Core tree data structure for the ACV interview model.
Represents the hierarchical structure of attributes, consequences and values.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple, Set
from .node import Node
from .node_label import NodeLabel
from ..models.trace_explanation_element import TraceExplanationElement

from .node import Node as NodeClass

logger = logging.getLogger(__name__)


class Tree:
    """
    Tree structure for representing the ACV interview model.
    Contains nodes organized in a hierarchical structure.
    """

    def __init__(self, root: Node):
        """
        Initialize a new tree with the given root node.

        Args:
            root: Root node of the tree
        """
        self.root = root
        self.active = self.root
        self.nodes_by_label: Dict[NodeLabel, List[Node]] = {
            label: [] for label in NodeLabel
        }
        # Optional: registriere Root unter seinem Label, falls gewünscht
        if self.root and self.root.get_label() in self.nodes_by_label:
            self.nodes_by_label[self.root.get_label()].append(self.root)

    def get_tree_root(self) -> Node:
        """Get the root node of the tree."""
        return self.root

    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        """
        Find a node by its ID (UUID string).

        Args:
            node_id: ID of the node to find (UUID string)

        Returns:
            The node with the given ID or None if not found
        """
        if node_id is None:
            return None
        for nodes in self.nodes_by_label.values():
            for n in nodes:
                if n.id == node_id:
                    return n
        return None

    def get_nodes_by_label(self, label: NodeLabel) -> List[Node]:
        """
        Get all nodes with the given label that have a conclusion.

        Args:
            label: Node label to filter by

        Returns:
            List of nodes with the given label and non-empty conclusion
        """
        return [
            node for node in self.nodes_by_label.get(label, [])
            if node.get_conclusion() is not None
        ]

    def get_nodes_path_to_root(self, node_obj: Node) -> List[Node]:
        """
        Get the path from the given node to the root.

        Args:
            node_obj: Starting node for the path

        Returns:
            List of nodes from the given node to the root
        """
        result: List[Node] = []
        visited: Set[str] = set()

        def dfs(current_node: Optional[Node]):
            if not current_node:
                return
            if current_node.id in visited:
                return
            visited.add(current_node.id)
            result.append(current_node)
            for parent in current_node.get_parents():
                dfs(parent)

        dfs(node_obj)
        return result

    def set_active_node(self, node_obj: Node):
        """
        Set the active node in the tree.

        Args:
            node_obj: Node to set as active
        """
        self.active = node_obj

    def add_stimulus(self, stimulus: str) -> Node:
        """
        Add a new stimulus to the existing tree and register it correctly
        in the nodes_by_label dictionary for later search operations.

        Args:
            stimulus: The new stimulus text

        Returns:
            The new stimulus node
        """
        if not self.root:
            raise ValueError("Cannot add stimulus to tree without a root node")

        # Create a new stimulus node
        stimulus_node = Node(
            label=NodeLabel.STIMULUS,
            conclusion=stimulus,
            parents=[self.root]
        )

        # Link to the root node
        self.root.add_child(stimulus_node)

        # Register node in the dictionary for later searches
        self.nodes_by_label[NodeLabel.STIMULUS].append(stimulus_node)

        logger.info(
            f"New stimulus node '{stimulus}' (ID: {stimulus_node.id}) created and registered"
        )
        return stimulus_node

    def add_child(self, label: NodeLabel, trace: List[TraceExplanationElement], conclusion: Optional[str] = None) -> Node:
        """
        Add a new child node to the active node.

        Args:
            label: Label of the new node
            trace: Trace elements explaining the node's creation
            conclusion: Optional conclusion text for the node

        Returns:
            The newly created node
        """
        new_node = Node(
            label=label,
            conclusion=conclusion,
            parents=[self.active],
            trace=trace
        )
        self.active.add_child(new_node)
        self.nodes_by_label[label].append(new_node)
        # Iteratively sets all parents to completed if new node is a value
        self.mark_value_path_completed(new_node)
        return new_node

    def add_existing_node_as_child(self, new_node: Node) -> Node:
        """
        Add an existing node as a child of the active node.
        This method is used for node sharing when a semantically similar node
        was found in another branch of the tree.

        Args:
            new_node: The existing node to add as a child

        Returns:
            The added node
        """
        # Check if the relationship already exists to avoid cycles
        if new_node in self.active.get_children() or self.active in new_node.get_parents():
            logger.warning(
                f"Node {new_node.id} is already a child of {self.active.id} - no action required"
            )
        else:
            # Create bidirectional link (parent-child relationship)
            new_node.add_parent(self.active)
            self.active.add_child(new_node)
            logger.info(
                f"Node {new_node.id} successfully shared as child of {self.active.id}"
            )

        return new_node

    def mark_value_path_completed(self, node_obj: Node) -> None:
        """
        Mark all nodes in the path from a value node to the root as completed.

        Args:
            node_obj: Node to start marking from (typically a value node)
        """
        if node_obj.label != NodeLabel.VALUE:
            return

        stack = [node_obj]
        visited: Set[str] = set()

        while stack:
            current = stack.pop()
            if current.id in visited:
                continue
            visited.add(current.id)
            current.is_value_path_completed = True

            # Add parents only if not already marked
            for parent in current.parents:
                if not parent.is_value_path_completed:
                    stack.append(parent)

    def remove_irrelevant_node(self) -> None:
        """Remove the current active node if it is an IRRELEVANT_ANSWER."""
        if self.active is None:
            logger.warning("Active node is None - cannot remove node")
            return

        if self.active.get_label() != NodeLabel.IRRELEVANT_ANSWER:
            logger.warning(
                f"Attempted removal of non-irrelevant node: {self.active.id}"
            )
            return

        irrelevant_node = self.active
        self.active = None  # Set active to None to remove the node

        # Remove the node from all parent relationships
        for parent in irrelevant_node.get_parents():
            parent.remove_child(irrelevant_node)

        # Remove the node from the label list
        if irrelevant_node in self.nodes_by_label[NodeLabel.IRRELEVANT_ANSWER]:
            self.nodes_by_label[NodeLabel.IRRELEVANT_ANSWER].remove(irrelevant_node)

        logger.info(f"Irrelevant node {irrelevant_node.id} successfully removed")

    def is_ancestor_of(self, potential_ancestor: Node, descendant: Node) -> bool:
        """Prüft, ob ein Knoten bereits ein Vorfahre eines anderen Knotens ist."""
        if not potential_ancestor or not descendant:
            return False

        # BFS-Suche nach Vorfahren
        visited: Set[str] = set()
        queue: List[Node] = [descendant]

        while queue:
            current = queue.pop(0)
            if current.id in visited:
                continue
            visited.add(current.id)

            # Alle Eltern prüfen
            for parent in current.get_parents():
                if parent.id == potential_ancestor.id:
                    return True  # Ist ein Vorfahre
                queue.append(parent)

        return False

    async def find_similar_node(self, label: NodeLabel, conclusion: str,
                                parent_node: Optional[Node] = None,
                                client=None, model=None, topic=None, stimulus=None) -> Tuple[Optional[Node], bool]:
        """
        Find a node with the same label and similar content.
        Uses optimized parallel context-based similarity checking via LLM.
        Special handling for Consequences: All parent Consequences are considered as potential matches.

        Args:
            label: The desired NodeLabel
            conclusion: The content to search for
            parent_node: Optional - An explicit parent node
            client: Optional - The LLM client for advanced similarity checking
            model: Optional - The LLM model to use
            topic: Optional - The interview topic for context
            stimulus: Optional - The interview stimulus for context

        Returns:
            Tuple (node, is_duplicate_under_parent):
            - If a similar/identical node is found, it is returned
            - The bool value indicates if it's a duplicate under the same parent node (ignore completely)
        """
        if not conclusion:
            return None, False

        conclusion_lower = conclusion.lower()

        # Storage for all potential matches
        similar_same_parent_matches: List[Node] = []  # Similar match under same parent node
        exact_diff_parent_matches: List[Node] = []    # Exact match in different branch
        similar_diff_parent_matches: List[Node] = []  # Similar match in different branch

        from ..analysis.similarity_analyzer import SimilarityAnalyzer

        # The actual parent node to use (parent_node takes precedence over active)
        effective_parent = parent_node if parent_node else self.active

        # Create temporary node for similarity checks
        new_node = NodeClass(label=label, conclusion=conclusion, parents=[effective_parent] if effective_parent else [])

        # Normal search in all nodes with the desired label
        for node_obj in self.nodes_by_label.get(label, []):
            node_conclusion = node_obj.get_conclusion()
            is_same_parent_context = False

            logger.debug(f"Examining node: {node_obj.id}")

            # Skip nodes without content
            if not node_conclusion:
                continue

            # 1. First check if a cycle would be created
            if effective_parent:
                # Check A: The node to check is identical to the parent node
                if effective_parent.id == node_obj.id:
                    logger.debug(
                        f"Potential cycle detected: Node {node_obj.id} is identical to the parent node"
                    )
                    is_same_parent_context = True
                # Check B: The node to check is already an ancestor of the parent node
                elif self.is_ancestor_of(node_obj, effective_parent):
                    is_same_parent_context = True
                    logger.debug(
                        f"Potential cycle detected: Node {node_obj.id} is already an ancestor of parent node {effective_parent.id}"
                    )

            # 2. Check text match
            is_exact_match = node_conclusion.lower() == conclusion_lower
            logger.debug(f"Is exact match: {is_exact_match}")

            # Normal similarity check for other nodes
            is_similar = not is_exact_match and SimilarityAnalyzer.is_similar_element(
                conclusion, node_conclusion, label
            )

            # 3. Categorize the node based on match and parent status
            if is_same_parent_context:
                if is_exact_match:
                    # CASE 1a: Exact match under same parent node - immediate return
                    logger.debug(
                        f"Exact duplicate found under same parent node: {node_obj.id} - '{node_conclusion}'"
                    )
                    return node_obj, True
                elif is_similar:
                    similar_same_parent_matches.append(node_obj)
                    logger.debug(
                        f"Similar element under same or indirect parent node: {node_obj.id} - '{node_conclusion}'"
                    )
            else:
                if is_exact_match:
                    exact_diff_parent_matches.append(node_obj)
                    logger.debug(
                        f"Exact match found in different branch: {node_obj.id} - '{node_conclusion}'"
                    )
                elif is_similar:
                    similar_diff_parent_matches.append(node_obj)
                    logger.debug(
                        f"Similar node found in different branch: {node_obj.id} - '{node_conclusion}'"
                    )

        # OPTIMIZATION: Parallel context-based check for all similar nodes
        if (similar_same_parent_matches or similar_diff_parent_matches) and client and model:
            # Collect all candidates for parallel checking
            all_candidates: List[Node] = []

            # First add same_parent candidates (have priority)
            all_candidates.extend(similar_same_parent_matches)

            # Then add diff_parent candidates
            all_candidates.extend(similar_diff_parent_matches)

            if all_candidates:
                logger.info(f"Checking {len(all_candidates)} similar nodes in parallel")
                try:
                    # Parallel similarity check for all candidates
                    similarity_results = await SimilarityAnalyzer.check_contextual_similarity(
                        new_node, all_candidates, self, client, model, topic, stimulus
                    )

                    # Process results
                    # 1. First look for same_parent nodes with high confidence
                    for result in similarity_results:
                        candidate_node = result.get("candidate_node")
                        should_merge = result.get("should_merge", False)
                        confidence = result.get("confidence_score", 0)
                        explanation = result.get("explanation", "")

                        # Check if node is from similar_same_parent_matches
                        if candidate_node in similar_same_parent_matches:
                            if confidence >= 70 and not should_merge:
                                logger.info(
                                    f"Context: Same-parent nodes are equal! Confidence: {confidence}%"
                                )
                                logger.debug(f"Explanation: {explanation}")
                                return candidate_node, True

                    # 2. If no same_parent match found, check diff_parent matches
                    best_match: Optional[Node] = None
                    best_confidence = 0

                    for result in similarity_results:
                        candidate_node = result.get("candidate_node")
                        should_merge = result.get("should_merge", False)
                        confidence = result.get("confidence_score", 0)

                        # Check if node is from similar_diff_parent_matches
                        if candidate_node in similar_diff_parent_matches:
                            if confidence >= 70 and should_merge and confidence > best_confidence:
                                best_match = candidate_node
                                best_confidence = confidence

                    if best_match:
                        logger.info(
                            f"Sharing: Diff-parent nodes should be shared! Confidence: {best_confidence}%"
                        )
                        return best_match, False

                except Exception as e:
                    logger.error(f"Error in parallel similarity check: {e}")

        # Exact matches in other branches for sharing
        if exact_diff_parent_matches:
            matched_node = exact_diff_parent_matches[0]
            logger.info(f"Sharing: Using exactly matching node: {matched_node.id}")
            return matched_node, False

        # No similar node found
        return None, False
