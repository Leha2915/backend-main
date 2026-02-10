"""
Utility functions for tree manipulation and analysis.
Provides methods for tree serialization, traversal and visualization.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from .node import Node
from .node_label import NodeLabel
from .tree import Tree

logger = logging.getLogger(__name__)


class TreeUtils:
    """
    Utility class for tree operations that don't belong in the core Tree class.
    """

    @staticmethod
    def to_json(tree: Tree) -> str:
        """
        Serialize the entire tree to JSON, including backwards relations.

        Args:
            tree: The tree to serialize

        Returns:
            JSON string representation of the tree
        """
        nodes_dict: Dict[str, Dict[str, Any]] = {}
        processed: Set[str] = set()

        # Create a map of ID to Node objects for quick access
        node_objects: Dict[str, Node] = {}

        # Phase 1: Capture normal nodes and relationships
        def add_node_to_dict(n: Node):
            if not n:
                return
            if n.id in processed:
                return
            processed.add(n.id)
            node_objects[n.id] = n  # Store Node object for later access

            # Correctly serialize trace elements
            traces = []
            for t in getattr(n, "trace", []):
                try:
                    # Serialize new format for trace_explanation_element
                    trace_data = {
                        "node_id": n.id,
                        "interaction_id": t.interaction_id if hasattr(t, "interaction_id") else None
                    }
                    traces.append(trace_data)
                except Exception as e:
                    logger.error(f"Error serializing trace element: {e}")
                    # Add empty element as fallback
                    traces.append({})

            nodes_dict[n.id] = {
                "id": n.id,
                "label": n.label.name if hasattr(n.label, "name") else str(n.label),
                "conclusion": n.conclusion,
                "parents": [p.id for p in getattr(n, "parents", [])],
                "children": [c.id for c in getattr(n, "children", [])],
                "backwards_relations": [],  # Placeholder for later
                "trace": traces,  # Use new trace serialization
                "is_value_path_completed": getattr(n, "is_value_path_completed", False),
                "created_ns": getattr(n, "created_ns", None),
            }

            # Recursively for all children
            for child in n.children:
                add_node_to_dict(child)

        # Start with the root node
        add_node_to_dict(tree.root)

        # Ensure active node and all nodes are captured
        if tree.active and tree.active.id not in processed:
            add_node_to_dict(tree.active)

        # Capture all nodes from nodes_by_label
        for label_nodes in tree.nodes_by_label.values():
            for n in label_nodes:
                if n.id not in processed:
                    add_node_to_dict(n)

        # Phase 2: Process backwards-relations
        logger.info("Processing backwards-relations in the tree...")

        # Collect IDEA nodes for later processing
        idea_nodes: List[Node] = []

        # Count total backwards-relations in the tree
        total_backwards = 0
        for node_id, node_obj in node_objects.items():
            backwards_relations = node_obj.get_backwards_relations()
            if backwards_relations:
                total_backwards += len(backwards_relations)

                # Identify IDEA nodes for later processing
                label = node_obj.label.name if hasattr(
                    node_obj.label, "name") else str(node_obj.label)
                if label == "IDEA":
                    idea_nodes.append(node_obj)

        logger.info(
            f"Found {total_backwards} total backwards-relations in the tree")
        logger.info(
            f"Found {len(idea_nodes)} IDEA nodes with backwards-relations (will be processed last)")

        # Phase 2a: Process ALL NON-IDEA NODES
        reorganized_count = 0
        for node_id, node_obj in node_objects.items():
            # Skip IDEA nodes - process later
            label = node_obj.label.name if hasattr(
                node_obj.label, "name") else str(node_obj.label)
            if label == "IDEA":
                continue

            backwards_relations = node_obj.get_backwards_relations()

            # Check if node has backwards_relations
            if backwards_relations:
                node_data = nodes_dict[node_id]

                logger.debug(
                    f"Node {label}({node_id}) has {len(backwards_relations)} backwards-relations")

                # STANDARD PROCESSING FOR NON-IDEA NODES
                for backwards_rel_node in backwards_relations:
                    backwards_rel_id = backwards_rel_node.id
                    backwards_rel_data = nodes_dict.get(backwards_rel_id)

                    if backwards_rel_data:
                        # Find IDEA-Parents of the backwards-relation node
                        idea_parents = []
                        for parent_id in list(backwards_rel_data["parents"]):
                            parent_data = nodes_dict.get(parent_id)
                            if parent_data and parent_data["label"] == "IDEA":
                                idea_parents.append(parent_id)

                        if idea_parents:
                            logger.debug(
                                f"Reorganizing relationship: {label}({node_id}) ← {backwards_rel_data['label']}({backwards_rel_id})")
                            reorganized_count += 1

                            # 1. Remove IDEA-Parents from the parents list of backwards-relation node
                            backwards_rel_data["parents"] = [
                                p for p in backwards_rel_data["parents"] if p not in idea_parents]

                            # 2. Add current node as parent if not already present
                            if node_id not in backwards_rel_data["parents"]:
                                backwards_rel_data["parents"].append(node_id)

                            # 3. Remove backwards-relation node from IDEA-Node children
                            for idea_id in idea_parents:
                                idea_data = nodes_dict.get(idea_id)
                                if idea_data and backwards_rel_id in idea_data["children"]:
                                    idea_data["children"].remove(
                                        backwards_rel_id)

                            # 4. Add backwards-relation node as child of current node
                            if backwards_rel_id not in node_data["children"]:
                                node_data["children"].append(backwards_rel_id)

        # Phase 2b: Process IDEA NODES (at the end)
        idea_reorganized_count = 0
        logger.info(
            f"Processing {len(idea_nodes)} IDEA nodes with backwards-relations...")

        for idea_node in idea_nodes:
            node_id = idea_node.id
            node_data = nodes_dict[node_id]
            backwards_relations = idea_node.get_backwards_relations()

            logger.debug(
                f"Special processing for IDEA node {node_id} with {len(backwards_relations)} backwards-relations")

            for backwards_rel_node in backwards_relations:
                backwards_rel_id = backwards_rel_node.id
                backwards_rel_data = nodes_dict.get(backwards_rel_id)
                backwards_rel_label = backwards_rel_node.label.name if hasattr(
                    backwards_rel_node.label, "name") else str(backwards_rel_node.label)

                if backwards_rel_data and backwards_rel_label == "ATTRIBUTE":
                    logger.debug(
                        f"Converting backwards-relation to normal relationship: IDEA({node_id}) → ATTRIBUTE({backwards_rel_id})")
                    idea_reorganized_count += 1

                    # 1. Ensure IDEA node is set as parent of the attribute
                    if node_id not in backwards_rel_data["parents"]:
                        backwards_rel_data["parents"].append(node_id)

                    # 2. Ensure attribute is set as child of IDEA node
                    if backwards_rel_id not in node_data["children"]:
                        node_data["children"].append(backwards_rel_id)

        logger.info(
            f"Reorganized {reorganized_count} standard backwards-relations in the tree")
        logger.info(
            f"Reorganized {idea_reorganized_count} IDEA backwards-relations in the tree")

        # Remove empty backwards_relations arrays for cleaner JSON
        for node_data in nodes_dict.values():
            if "backwards_relations" in node_data and len(node_data["backwards_relations"]) == 0:
                del node_data["backwards_relations"]

        # Create a "complete tree" object
        tree_data = {
            "nodes": list(nodes_dict.values()),
            "active_node_id": tree.active.id if tree.active else None,
            "root_node_id": tree.root.id if tree.root else None
        }

        return json.dumps(tree_data, ensure_ascii=False, indent=2)

    @staticmethod
    def to_ascii_tree(tree: Tree) -> str:
        """
        Create a simple ASCII representation of the tree.

        Args:
            tree: The tree to visualize

        Returns:
            ASCII string representation of the tree
        """
        if not tree:
            return "No tree available"

        root = tree.get_tree_root()
        if not root:
            return "Tree has no root node"

        # Use a set to track visited nodes and prevent cycles
        visited: Set[str] = set()

        def _build_tree_str(node: Node, prefix: str = "", is_last: bool = True):
            if not node or node.id in visited:
                return ""

            # Mark node as visited to prevent cycles
            visited.add(node.id)

            result = ""
            active_marker = " [ACTIVE]" if node == tree.active else ""

            result += prefix
            result += "└── " if is_last else "├── "

            label = node.get_label().value if hasattr(node, 'get_label') else '?'
            conclusion = node.get_conclusion()
            if conclusion and len(conclusion) > 30:
                conclusion = conclusion[:27] + "..."
            result += f"{label}({node.id}): {conclusion or 'No description'}{active_marker}\n"

            # Only process children that haven't been visited yet
            unvisited_children = [
                c for c in node.children if c.id not in visited]
            child_count = len(unvisited_children)

            for i, child in enumerate(unvisited_children):
                new_prefix = prefix + ("    " if is_last else "│   ")
                is_last_child = i == (child_count - 1)
                result += _build_tree_str(child, new_prefix, is_last_child)

            return result

        # Root node display
        active_marker = " [ACTIVE]" if root == tree.active else ""
        result = f"{root.get_label().value}({root.id}): {root.get_conclusion() or 'No description'}{active_marker}\n"

        # Only process children that haven't been visited yet
        children = [c for c in root.children if c.id not in visited]
        child_count = len(children)

        for i, child in enumerate(children):
            is_last_child = i == (child_count - 1)
            result += _build_tree_str(child, "", is_last_child)

        return result

    @staticmethod
    def merge_trees_with_topic(topic: str, trees: List[Tree]) -> Tree:
        """
        Create a new Tree with a common topic node as root
        and add all provided trees as subtrees beneath it.

        With UUIDs we do not renumber IDs. We simply link subroots under the topic node.
        Optionally, an 'order_index' attribute is set on subroots to preserve order.
        """
        from .node import Node as NodeClass

        logger.info(f"Merging {len(trees)} trees under topic '{topic}'")

        # Create Topic node with its own UUID
        topic_node = NodeClass(label=NodeLabel.TOPIC, conclusion=topic)
        logger.debug(f"Topic node created with ID: {topic_node.id}")

        # Initialize new tree with Topic Node as root
        merged_tree = Tree(root=topic_node)
        merged_tree.nodes_by_label[NodeLabel.TOPIC].append(topic_node)

        # Optional: preserve order of stimuli
        order_counter = 0

        # Iterate through all subtrees
        for i, sub_tree in enumerate(trees):
            if not sub_tree or not hasattr(sub_tree, 'root') or not sub_tree.root:
                logger.warning(f"Skipping empty/invalid subtree #{i}")
                continue

            sub_root = sub_tree.root

            # Create bidirectional relationship without ID reassignment
            sub_root.add_parent(topic_node)
            topic_node.add_child(sub_root)

            # Optional: store order index on the subroot (useful for UI sorting)
            try:
                setattr(sub_root, "order_index", order_counter)
                order_counter += 1
            except Exception:
                pass

            # Collect all nodes from the subtree and register them to the merged tree
            for label, node_list in sub_tree.nodes_by_label.items():
                for node_obj in node_list:
                    if node_obj not in merged_tree.nodes_by_label[label]:
                        merged_tree.nodes_by_label[label].append(node_obj)

        total_nodes = sum(len(nodes)
                          for nodes in merged_tree.nodes_by_label.values())
        logger.info(f"Merged tree created with {total_nodes} total nodes")

        return merged_tree

    @staticmethod
    def build_optimized_path_excluding_irrelevant(interview_tree: Tree, active_node: Node) -> List[Node]:
        """
        Builds an optimized path from active node to root,
        always choosing the newest parent path (by created_ns) and excluding irrelevant nodes.

        Args:
            interview_tree: Interview tree
            active_node: Active node

        Returns:
            List of nodes from active node to root (excluding irrelevant nodes)
        """
        if not interview_tree or not active_node:
            return []

        # Start with active node
        current = active_node
        path_nodes = [current]

        # Follow path of newest parents (latest created_ns)
        # but skip irrelevant nodes
        while current:
            parent = current.get_latest_parent()
            if not parent:
                break

            # Skip irrelevant nodes in path
            if parent.get_label() == NodeLabel.IRRELEVANT_ANSWER:
                logger.debug(f"Skipping irrelevant node in path: {parent.id}")
                # Try to find parent of irrelevant node
                grandparents = parent.get_parents()
                if grandparents:
                    parent = grandparents[0]  # Use first grandparent node
                    logger.debug(
                        f"Using grandparent node: {parent.id} - {parent.get_label().value}")
                else:
                    break  # No more parents available

            path_nodes.append(parent)
            current = parent

        return path_nodes

    @staticmethod
    def build_context_path_from_node(tree: 'Tree', node: Optional[Node]) -> str:
        """
        Builds a formatted path string from a node to root,
        choosing the latest parent path and filtering out auto-generated nodes.

        This method creates a user-friendly path representation for LLM context.

        Args:
            tree: The tree containing the node
            node: The starting node (typically the active node)

        Returns:
            A formatted path string (e.g. "VALUE: Safety → CONSEQUENCE: Prevents accidents")
        """
        if not tree or not node:
            return ""

        # Start with the node
        current = node
        path_nodes = [current]

        # Follow the path of the latest parents (based on created_ns via get_latest_parent)
        while current:
            parent = current.get_latest_parent()
            if not parent:
                break

            path_nodes.append(parent)
            current = parent

        # Filter out AUTO-generated nodes
        filtered_path_nodes = []
        for node_obj in path_nodes:
            conclusion = node_obj.get_conclusion() or ""
            # Check if the node is auto-generated (starts with "AUTO:" or "DUMMY-")
            if not conclusion.startswith(("AUTO:", "DUMMY-")):
                filtered_path_nodes.append(node_obj)

        # If all nodes were filtered, return empty string
        if not filtered_path_nodes:
            return ""

        # Format the filtered path
        return " → ".join([
            f"{n.get_label().value}: {n.get_conclusion()}"
            for n in filtered_path_nodes
        ])

    @staticmethod
    def format_chains_for_response(tree_obj: Tree) -> List[Dict[str, Any]]:
        """
        Format attribute-consequence-value chains for the response.

        This method extracts chains from the tree in a structured format,
        organizing them by attributes with their associated consequences and values.

        Args:
            tree_obj: Interview tree object

        Returns:
            List of dictionaries representing ACV chains
        """
        chains = []

        if not tree_obj:
            return chains

        attributes = tree_obj.get_nodes_by_label(NodeLabel.ATTRIBUTE)

        for attr_node in attributes:
            chain = {
                "Attribute": attr_node.get_conclusion() or "",
                "Consequence": [],
                "Values": []
            }

            # Find consequences for this attribute
            for cons_node in tree_obj.get_nodes_by_label(NodeLabel.CONSEQUENCE):
                path = tree_obj.get_nodes_path_to_root(cons_node)
                if attr_node in path:
                    chain["Consequence"].append(
                        cons_node.get_conclusion() or "")

                    # Find values for this consequence
                    for val_node in tree_obj.get_nodes_by_label(NodeLabel.VALUE):
                        val_path = tree_obj.get_nodes_path_to_root(val_node)
                        if cons_node in val_path:
                            chain["Values"].append(
                                val_node.get_conclusion() or "")

            chains.append(chain)

        return chains

    @staticmethod
    def is_direct_or_indirect_child(potential_parent: Node, potential_child: Node) -> bool:
        """
        Check if a node is a direct or indirect child of another node.
        Ignores dummy nodes and AUTO-generated nodes in the path to the parent node.

        Args:
            potential_parent: The potential parent node
            potential_child: The potential child node

        Returns:
            True if potential_child is a direct or indirect child of potential_parent
            (ignoring dummy nodes or AUTO-generated nodes in the path)
        """
        if not potential_parent or not potential_child:
            return False

        # Helper function to detect dummy nodes and AUTO-generated nodes
        def is_artificial_node(node_obj: Node) -> bool:
            """Check if a node is a dummy node or AUTO-generated."""
            if not node_obj:
                return False

            # Check for IRRELEVANT_ANSWER label
            if node_obj.get_label() == NodeLabel.IRRELEVANT_ANSWER:
                return True

            # Get the conclusion of the node
            conclusion = node_obj.get_conclusion()
            if not conclusion:
                return False

            # Check for DUMMY prefix
            if conclusion.startswith("DUMMY-"):
                return True

            # Check for AUTO prefix (from PromptAnalyzer)
            if conclusion.startswith("AUTO: "):
                return True

            return False

        # Direct check: Is potential_parent among the parents of potential_child?
        direct_parents = [parent for parent in potential_child.get_parents()
                          if not is_artificial_node(parent)]

        if potential_parent in direct_parents:
            logger.info(
                f"Direct child found: {potential_child.id} is direct child of {potential_parent.id}")
            return True

        # Indirect check: BFS through all ancestors of potential_child (without artificial nodes)
        visited: Set[str] = set()
        queue = [parent for parent in potential_child.get_parents()
                 if not is_artificial_node(parent)]

        while queue:
            current_parent = queue.pop(0)

            # Avoid cycles
            if current_parent.id in visited:
                continue
            visited.add(current_parent.id)

            # Check if the desired parent node is found
            if current_parent.id == potential_parent.id:
                logger.info(
                    f"Indirect child found: {potential_child.id} is indirect child of {potential_parent.id}")
                return True

            # Add only real (non-artificial) parents to the queue
            real_parents = [parent for parent in current_parent.get_parents()
                            if not is_artificial_node(parent)]
            queue.extend(real_parents)

            # Debug output for ignored artificial nodes
            artificial_parents = [
                parent for parent in current_parent.get_parents() if is_artificial_node(parent)]
            for artificial in artificial_parents:
                conclusion = artificial.get_conclusion() or ""
                node_type = "DUMMY" if conclusion.startswith("DUMMY-") else \
                            "AUTO" if conclusion.startswith("AUTO: ") else \
                            "IRRELEVANT" if artificial.get_label() == NodeLabel.IRRELEVANT_ANSWER else "UNKNOWN"
                logger.debug(
                    f"{node_type} node {artificial.id} ignored in path (Conclusion: '{conclusion}')")

        logger.debug(
            f"No relationship: {potential_child.id} is NOT a child of {potential_parent.id} (without artificial paths)")
        return False

    @staticmethod
    def debug_tree(tree: Tree, logger=None):
        """
        Provides debug information about the current tree state.

        Args:
            tree: The tree to debug
            logger: Optional logger instance (falls back to print if None)
        """
        if not tree:
            if logger:
                logger.warning("⚠️ No tree available!")
            else:
                print("⚠️ No tree available!")
            return

        # Basic tree data
        log_msg = "\n📊 TREE DEBUG INFO:"
        log_msg += f"\n  Root (Stimulus): {tree.root.get_conclusion() if tree.root else 'None'}"
        log_msg += f"\n  Active Node: ID={tree.active.id}, Label={tree.active.get_label().value if tree.active else 'None'}"

        # Nodes by label
        for label in NodeLabel:
            nodes = tree.get_nodes_by_label(label)
            log_msg += f"\n  {label.value} nodes: {len(nodes)}"
            for i, n in enumerate(nodes):
                parent_ids = [p.id for p in n.parents]
                child_ids = [c.id for c in n.children]
                log_msg += f"\n    - ID: {n.id}, Conclusion: '{(n.get_conclusion() or '')[:20]}...', Parents: {parent_ids}, Children: {child_ids}"

        # Path from active node to root
        if tree.active:
            path = tree.get_nodes_path_to_root(tree.active)
            path_str = " → ".join(
                [f"{n.get_label().value}({n.id})" for n in path])
            log_msg += f"\n  Path to Root: {path_str}"

        # ASCII tree output
        log_msg += "\n\n🌳 Current Tree State (visual):"
        if hasattr(TreeUtils, 'to_ascii_tree'):
            log_msg += "\n" + TreeUtils.to_ascii_tree(tree)
        else:
            log_msg += "\nASCII Tree function not available"

        # Output the message
        if logger:
            logger.info(log_msg)
        else:
            print(log_msg)

    @staticmethod
    def to_dict(tree: Tree) -> Dict[str, Any]:
        """
        Convert a tree to a dictionary representation for serialization.

        Args:
            tree: The tree to convert

        Returns:
            Dictionary representation of the tree
        """
        all_nodes: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()

        # Collect all nodes in the tree, not just the reachable ones
        def collect_all_nodes():
            # Always add root node and active node
            if tree.root and tree.root.id not in seen_ids:
                seen_ids.add(tree.root.id)
                all_nodes.append(tree.root.to_dict())

            if tree.active and tree.active.id not in seen_ids:
                seen_ids.add(tree.active.id)
                all_nodes.append(tree.active.to_dict())

            # Collect all registered nodes from nodes_by_label
            for _, nodes_list in tree.nodes_by_label.items():
                for n in nodes_list:
                    if n.id not in seen_ids:
                        seen_ids.add(n.id)
                        all_nodes.append(n.to_dict())

        # Collect recursively (old code)
        def collect_nodes_recursively(n: Optional[Node]):
            if not n or n.id in seen_ids:
                return
            seen_ids.add(n.id)
            all_nodes.append(n.to_dict())
            for child in n.get_children():
                collect_nodes_recursively(child)

        # Use both methods for maximum robustness
        collect_nodes_recursively(tree.root)
        # Ensures that nodes not reachable via children are also captured
        collect_all_nodes()

        return {
            "root_node_id": tree.root.id if tree.root else None,
            "active_node_id": tree.active.id if tree.active else None,
            "nodes": all_nodes,
            # Removed: next_id_counter (no global counter with UUIDs)
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Tree:
        """
        Create a tree from a dictionary representation.

        Args:
            data: Dictionary representation of the tree

        Returns:
            The reconstructed tree
        """
        from .node import Node as NodeClass

        nodes_by_id: Dict[str, Node] = {}
        all_nodes_data = data.get("nodes", [])

        if not all_nodes_data:
            logger.warning(
                "Empty node list when loading tree! Creating minimal tree.")
            # Create a dummy root node
            stimulus_text = data.get(
                "stimulus_text", "Voice-controlled assistants")
            stimulus_node = NodeClass(NodeLabel.STIMULUS, conclusion=stimulus_text)

            # Create and configure a minimal tree
            tree_instance = Tree(stimulus_node)
            tree_instance.nodes_by_label[NodeLabel.STIMULUS].append(
                stimulus_node)

            return tree_instance

        # 1. Create all node objects and store them in a dictionary
        for node_data in all_nodes_data:
            n = NodeClass.from_dict(node_data)
            nodes_by_id[str(n.id)] = n

        # 2. Restore parent-child relationships in BOTH directions
        for node_data in all_nodes_data:
            current_node = nodes_by_id[str(node_data["id"])]
            # Set parents
            for parent_id in node_data.get("parents", []):
                parent = nodes_by_id.get(str(parent_id))
                if parent:
                    current_node.add_parent(parent)
                    # Important: Relationship in both directions
                    parent.add_child(current_node)
            # Restore trace elements
            trace_data = node_data.get("trace", [])
            from ..models.trace_explanation_element import TraceExplanationElement
            for trace_dict in trace_data:
                interaction_id = trace_dict.get("interaction_id")
                ref_node_id = str(trace_dict.get("node_id")) if trace_dict.get("node_id") else None
                trace_node = nodes_by_id.get(ref_node_id) if ref_node_id else None
                trace_elem = TraceExplanationElement(
                    interaction_id, trace_node)
                current_node.add_trace(trace_elem)

        # 2b. Set backwards relations afterwards
        for n in nodes_by_id.values():
            if hasattr(n, "_pending_backwards_relations"):
                for rel_id in n._pending_backwards_relations:
                    rel_node = nodes_by_id.get(str(rel_id))
                    if rel_node:
                        n.add_backwards_relation(rel_node)
                del n._pending_backwards_relations

        # 3. Create tree instance and configure
        root_id = str(data["root_node_id"])
        root_node = nodes_by_id[root_id]
        tree_instance = Tree(root_node)

        # 4. Register nodes in nodes_by_label
        for node_obj in nodes_by_id.values():
            label = node_obj.get_label()
            if label in tree_instance.nodes_by_label:
                tree_instance.nodes_by_label[label].append(node_obj)

        # 5. Set active node
        active_id = data.get("active_node_id")
        if active_id is not None and str(active_id) in nodes_by_id:
            tree_instance.set_active_node(nodes_by_id[str(active_id)])

        # 6. No global ID counter to restore (UUIDs)
        return tree_instance
