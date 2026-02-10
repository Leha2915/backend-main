"""
Test script for node deduplication and sharing functionality.
This script provides a standalone implementation to test the node sharing logic
without external dependencies.
"""

# Define minimal versions of required classes to avoid dependencies
class NodeLabel:
    TOPIC = "TOPIC"
    STIMULUS = "STIMULUS"
    IDEA = "IDEA"
    ATTRIBUTE = "ATTRIBUTE"
    CONSEQUENCE = "CONSEQUENCE"
    VALUE = "VALUE"
    IRRELEVANT_ANSWER = "IRRELEVANT_ANSWER"

class TraceElement:
    def __init__(self, node, interaction_id=None):
        self.node = node
        self.interaction_id = interaction_id or "test_interaction"
    
    def get_interaction_id(self):
        return self.interaction_id

class Node:
    _id_counter = 0
    
    def __init__(self, label, conclusion=None, parents=None, trace=None):
        self.id = Node._id_counter
        Node._id_counter += 1
        
        self.label = label
        self.conclusion = conclusion
        self.parents = parents or []
        self.children = []
        self.trace = trace or []
        self.is_value_path_completed = label == NodeLabel.VALUE
    
    def get_parents(self):
        return self.parents
    
    def get_children(self):
        return self.children
    
    def get_label(self):
        return self.label
    
    def get_conclusion(self):
        return self.conclusion
    
    def add_child(self, child):
        if child not in self.children:
            self.children.append(child)
    
    def add_parent(self, parent):
        if parent not in self.parents:
            self.parents.append(parent)
    
    def add_trace(self, trace_element):
        if trace_element not in self.trace:
            self.trace.append(trace_element)

class PromptAnalyzer:
    @classmethod
    def _is_similar_element(cls, element1, element2, element_type=None):
        """Simplified version of semantic similarity detection"""
        if not element1 or not element2:
            return False
            
        # Normalize strings
        element1 = element1.lower().strip()
        element2 = element2.lower().strip()
        
        # Exact match
        if element1 == element2:
            return True
        
        # Substring check for shorter texts
        if len(element1) <= 30 or len(element2) <= 30:
            if element1 in element2 or element2 in element1:
                return True
        
        # Word comparison
        words1 = set(element1.split())
        words2 = set(element2.split())
        common_words = words1.intersection(words2)
        
        # Check word similarity
        if len(common_words) >= 2 or (common_words and (len(common_words) / max(len(words1), len(words2)) >= 0.3)):
            return True
            
        # Type-specific synonyms
        if element_type == NodeLabel.VALUE:
            value_terms = {
                "freedom": ["freedom", "free", "liberty", "independence"],
                "control": ["control", "controlling", "controlled"]
            }
            
            for term_group in value_terms.values():
                has_term1 = any(term in element1 for term in term_group)
                has_term2 = any(term in element2 for term in term_group)
                if has_term1 and has_term2:
                    return True
        
        return False

class Tree:
    def __init__(self, topic, stimuli):
        self.root = Node(NodeLabel.TOPIC, conclusion=topic)
        self.active = self.root
        self.nodes_by_label = {label: [] for label in [NodeLabel.TOPIC, NodeLabel.STIMULUS, 
                                                      NodeLabel.IDEA, NodeLabel.ATTRIBUTE, 
                                                      NodeLabel.CONSEQUENCE, NodeLabel.VALUE]}
        self.nodes_by_label[NodeLabel.TOPIC] = [self.root]
        
        # Add stimuli as children of root
        for stim in stimuli:
            stim_node = Node(label=NodeLabel.STIMULUS, conclusion=stim, parents=[self.root])
            self.root.add_child(stim_node)
            self.nodes_by_label[NodeLabel.STIMULUS].append(stim_node)
    
    def get_tree_root(self):
        return self.root
    
    def get_nodes_by_label(self, label):
        return self.nodes_by_label.get(label, [])
    
    def set_active_node(self, node_obj):
        self.active = node_obj
    
    def add_child(self, label, trace, conclusion=None):
        new_node = Node(
            label=label,
            conclusion=conclusion,
            parents=[self.active],
            trace=trace
        )
        self.active.add_child(new_node)
        self.nodes_by_label[label].append(new_node)
        self.set_active_node(new_node)
        return new_node
    
    def add_existing_node_as_child(self, new_node):
        """
        Add an existing node as a child of the active node.
        This method is used for node sharing when a semantically similar node
        is found in another branch of the tree.
        """
        # Check if the relationship already exists to avoid cycles
        if new_node in self.active.get_children() or self.active in new_node.get_parents():
            print(f"⚠️ Node {new_node.id} is already a child of {self.active.id} - no action required")
        else:
            # Create bidirectional link (parent-child relationship)
            new_node.add_parent(self.active)
            self.active.add_child(new_node)
            print(f"Node {new_node.id} successfully shared as child of {self.active.id}")
            
        # Set active node to the new node
        self.set_active_node(new_node)
        return new_node
    
    def find_similar_node(self, label, conclusion, parent_node=None):
        """
        Finds a node with the same label and similar content.
        Implements advanced deduplication and node sharing logic:
        1. Duplicates under the same parent are ignored (return None)
        2. Semantically similar nodes in other branches are found and can be shared
        
        Args:
            label: The NodeLabel to search for
            conclusion: The content to search for
            parent_node: Optional - The parent node under which to search for duplicates.
                         If provided, duplicates under this parent node are ignored.
            
        Returns:
            A matching node or None if none was found
        """
        if not conclusion:
            return None
            
        conclusion_lower = conclusion.lower()
        
        # Store all potential matches
        exact_matches = []
        similar_matches = []
        
        # Search in all nodes with the requested label
        for node_obj in self.nodes_by_label.get(label, []):
            node_conclusion = node_obj.get_conclusion()
            
            # Skip nodes without content
            if not node_conclusion:
                continue
                
            # CASE 1: Check for duplicates under the same parent or active node
            is_child_of_active = self.active in node_obj.get_parents()
            is_child_of_parent = parent_node and parent_node in node_obj.get_parents()
            
            if is_child_of_parent or is_child_of_active:
                # Exact match under same parent - ignore
                if node_conclusion.lower() == conclusion_lower:
                    parent_id = parent_node.id if parent_node else self.active.id
                    print(f"Exact match found under parent node {parent_id}: {node_obj.id} - {node_conclusion}")
                    return None
                
                # Semantic similarity under same parent - ignore
                if PromptAnalyzer._is_similar_element(conclusion, node_conclusion, label):
                    parent_id = parent_node.id if parent_node else self.active.id
                    print(f"Similar node found under parent node {parent_id}: {node_obj.id} - {node_conclusion}")
                    return None
            
            # CASE 2: Collect matches in other branches (for sharing)
            else:
                # Exact match in another branch
                if node_conclusion.lower() == conclusion_lower:
                    exact_matches.append(node_obj)
                    print(f"Exact match found in another branch: {node_obj.id} - {node_conclusion}")
                
                # Semantic similarity in another branch
                elif PromptAnalyzer._is_similar_element(conclusion, node_conclusion, label):
                    similar_matches.append(node_obj)
                    print(f"Similar node found in another branch: {node_obj.id} - {node_conclusion}")
        
        # Priority: Exact matches > Semantic similarities
        if exact_matches:
            # Return the first exact match
            print(f"✅ Sharing: Using exact matching node: {exact_matches[0].id}")
            return exact_matches[0]
        
        if similar_matches:
            # Return the first semantically similar match
            print(f"✅ Sharing: Using semantically similar node: {similar_matches[0].id}")
            return similar_matches[0]
        
        # No similar node found
        return None

def test_node_deduplication_and_sharing():
    """Test the node deduplication and sharing functionality."""
    print("\n=== Testing Node Deduplication and Sharing ===\n")
    
    # Create a test tree with a topic and two stimuli
    tree = Tree("Test Topic", ["Stimulus A", "Stimulus B"])
    
    # Get the root and stimulus nodes
    root = tree.get_tree_root()
    stimuli = tree.get_nodes_by_label(NodeLabel.STIMULUS)
    stimulus_a = stimuli[0]
    stimulus_b = stimuli[1]
    
    print(f"Root node: {root.id} - {root.get_conclusion()}")
    print(f"Stimulus A: {stimulus_a.id} - {stimulus_a.get_conclusion()}")
    print(f"Stimulus B: {stimulus_b.id} - {stimulus_b.get_conclusion()}")
    
    # Add an idea under stimulus A
    tree.set_active_node(stimulus_a)
    idea_a = tree.add_child(NodeLabel.IDEA, [], "Test Idea")
    print(f"\nAdded Idea under Stimulus A: {idea_a.id} - {idea_a.get_conclusion()}")
    
    # Add an attribute under idea A
    tree.set_active_node(idea_a)
    attribute_a = tree.add_child(NodeLabel.ATTRIBUTE, [], "Test Attribute")
    print(f"Added Attribute under Idea A: {attribute_a.id} - {attribute_a.get_conclusion()}")
    
    # Add a consequence under the attribute
    tree.set_active_node(attribute_a)
    consequence_a = tree.add_child(NodeLabel.CONSEQUENCE, [], "Test Consequence")
    print(f"Added Consequence under Attribute A: {consequence_a.id} - {consequence_a.get_conclusion()}")
    
    # Now try to add the same attribute under the same idea (should be ignored)
    tree.set_active_node(idea_a)
    similar_node = tree.find_similar_node(NodeLabel.ATTRIBUTE, "Test Attribute", idea_a)
    print(f"\nTrying to add duplicate attribute under same Idea: {'Ignored' if similar_node is None else 'Failed - returned a node'}")
    
    # Try to add a slightly different attribute under the same idea
    tree.set_active_node(idea_a)
    similar_node = tree.find_similar_node(NodeLabel.ATTRIBUTE, "Test Attribute with slight variation", idea_a)
    if similar_node is None:
        attribute_a2 = tree.add_child(NodeLabel.ATTRIBUTE, [], "Test Attribute with slight variation")
        print(f"Added different Attribute under same Idea: {attribute_a2.id} - {attribute_a2.get_conclusion()}")
    else:
        print(f"Failed - incorrectly identified as similar: {similar_node.id}")
    
    # Add an idea under stimulus B
    tree.set_active_node(stimulus_b)
    idea_b = tree.add_child(NodeLabel.IDEA, [], "Different Test Idea")
    print(f"\nAdded Idea under Stimulus B: {idea_b.id} - {idea_b.get_conclusion()}")
    
    # Try to add the same attribute under idea B (should find the existing one and create a new parent-child relationship)
    tree.set_active_node(idea_b)
    similar_node = tree.find_similar_node(NodeLabel.ATTRIBUTE, "Test Attribute", idea_b)
    if similar_node:
        # Add the existing node as a child of idea_b
        tree.add_existing_node_as_child(similar_node)
        print(f"Found similar Attribute in another branch: {similar_node.id} - {similar_node.get_conclusion()}")
        print(f"  Parents of this Attribute: {[p.id for p in similar_node.get_parents()]}")
        print(f"  This Attribute now has {len(similar_node.get_parents())} parents")
    else:
        print("Failed - did not identify the similar attribute")
    
    # Try to add a semantically similar attribute (should find the existing one)
    tree.set_active_node(idea_b)
    similar_node = tree.find_similar_node(NodeLabel.ATTRIBUTE, "Attribute for testing", idea_b)
    if similar_node:
        tree.add_existing_node_as_child(similar_node)
        print(f"\nFound semantically similar Attribute: {similar_node.id} - {similar_node.get_conclusion()}")
        print(f"  Parents of this Attribute: {[p.id for p in similar_node.get_parents()]}")
    else:
        print("\nFailed - did not identify the semantically similar attribute")
    
    # Test values with multiple parents
    # First add a value under consequence_a
    tree.set_active_node(consequence_a)
    value_a = tree.add_child(NodeLabel.VALUE, [], "Test Value about freedom and control")
    print(f"\nAdded Value under Consequence A: {value_a.id} - {value_a.get_conclusion()}")
    
    # Add a different consequence under attribute_a
    tree.set_active_node(attribute_a)
    consequence_b = tree.add_child(NodeLabel.CONSEQUENCE, [], "Different Test Consequence")
    print(f"Added different Consequence under Attribute A: {consequence_b.id} - {consequence_b.get_conclusion()}")
    
    # Try to add a semantically similar value under consequence_b
    tree.set_active_node(consequence_b)
    similar_node = tree.find_similar_node(NodeLabel.VALUE, "Value about feeling free and in control", consequence_b)
    if similar_node:
        tree.add_existing_node_as_child(similar_node)
        print(f"Found semantically similar Value: {similar_node.id} - {similar_node.get_conclusion()}")
        print(f"  Parents of this Value: {[p.id for p in similar_node.get_parents()]}")
        print(f"  This Value now has {len(similar_node.get_parents())} parents")
    else:
        print("Failed - did not identify the semantically similar value")
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    test_node_deduplication_and_sharing()
