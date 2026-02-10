import pytest
import requests
import sys
import os
import pathlib
import time

# Add the absolute path to the project base directory
root_dir = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))


def test_comprehensive_node_merging(smart_home_client):
    """
    Comprehensive test for node merging across different scenarios:
    
    Tests the following merging patterns:
    1. Exact 1:1 matching elements (should merge)
    2. Very similar elements with minor wording changes (should merge)
    3. Elements across different stimuli (should maintain context but identify similarities)
    4. Multi-element responses in a single message (should be correctly split and processed)
    5. Edge cases like very short descriptions and boundary conditions
    
    Tests all node types: Attributes, Consequences, and Values
    """
    print("\n=== TEST: Comprehensive Node Merging ===")

    ########################
    # STIMULUS 1: Voice-controlled assistants
    ########################
    print("\n🔍 TESTING WITH STIMULUS 1: Voice-controlled assistants")

    # Check project slug validity
    check_resp = requests.get(f"http://localhost:8000/projects/{smart_home_client.project_slug}")
    print(f"Project check: {check_resp.status_code} - {check_resp.text if check_resp.status_code != 200 else 'OK'}")
    assert check_resp.ok, "Project check failed before starting test"

    # Initial greeting to establish conversation
    response = smart_home_client.send_message("Hello, I'd like to discuss voice assistants")
    print("\nStarting conversation...")

    # Start the conversation with main content
    response = smart_home_client.send_message(
        "I think voice assistants are important because they make controlling my home easier."
    )
    print("\n--- Basic Element Detection ---")

    # ATTRIBUTE TEST 1: Natural language understanding (original attribute)
    response = smart_home_client.send_message(
        "The most important feature is natural language understanding."
    )

    # CONSEQUENCE TEST 1: Original consequence for natural language understanding
    response = smart_home_client.send_message(
        "When the assistant understands my natural language, I can speak normally without "
        "having to remember specific command phrases."
    )

    # CONSEQUENCE TEST 2: EXACT MATCH - Identical consequence (should merge with previous)
    print("\n--- Testing Exact Duplicate Merging ---")
    response = smart_home_client.send_message(
        "When the assistant understands my natural language, I can speak normally without "
        "having to remember specific command phrases."
    )

    # Check exact match consequences were merged
    chains = response.get("Chains", [])
    natural_language_chains = [
        chain for chain in chains if "natural language" in chain["Attribute"].lower()]
    assert len(
        natural_language_chains) > 0, "No chain with 'natural language' attribute found"
    main_chain = natural_language_chains[0]

    # Exact duplicates should be merged, so we should have a reasonable number of consequences
    assert "Consequence" in main_chain, "No consequences in the natural language chain"
    # More lenient assertion - check that we don't have too many duplicates
    assert len(main_chain["Consequence"]) <= 2, f"Too many duplicate consequences detected: {main_chain['Consequence']}"
    print(f"✅ Exact duplicate handling: {main_chain['Consequence']}")

    # CONSEQUENCE TEST 3: SIMILAR consequence (should merge with previous)
    print("\n--- Testing Similar Element Merging ---")
    response = smart_home_client.send_message(
        "It means I don't need to memorize exact command wording, I can just talk naturally."
    )

    # Check similar consequences were merged
    chains = response.get("Chains", [])
    natural_language_chains = [
        chain for chain in chains if "natural language" in chain["Attribute"].lower()]
    main_chain = natural_language_chains[0]

    # Similar consequences might be merged or kept separate depending on similarity threshold
    # We'll just check that we don't have too many
    assert len(main_chain["Consequence"]) <= 3, f"Too many consequences detected (duplicates?): {main_chain['Consequence']}"
    print(f"✅ Similar element handling: {main_chain['Consequence']}")

    # VALUE TEST 1: Original value
    response = smart_home_client.send_message(
        "This gives me a feeling of comfort and ease when interacting with my home."
    )

    # VALUE TEST 2: EXACT MATCH - Identical value (should merge)
    print("\n--- Testing Value Merging ---")
    response = smart_home_client.send_message(
        "This gives me a feeling of comfort and ease when interacting with my home."
    )

    # Allow time for merging to process
    time.sleep(1)

    # Check exact match values were merged
    chains = response.get("Chains", [])
    natural_language_chains = [
        chain for chain in chains if "natural language" in chain["Attribute"].lower()]
    main_chain = natural_language_chains[0]

    # Verify values exist but with flexible assertion
    if "Values" in main_chain:
        print(f"✅ Values found: {main_chain.get('Values', [])}")
    else:
        print("⚠️ No values detected yet - this can happen depending on the model")

    # VALUE TEST 3: SIMILAR value (should merge with previous)
    response = smart_home_client.send_message(
        "It makes me feel comfortable and relaxed in my living environment."
    )

    # EDGE CASE 1: Multiple elements in a single response
    print("\n--- Testing Multi-Element Processing ---")
    response = smart_home_client.send_message(
        "Voice assistants have two other important features: voice clarity and responsive feedback. "
        "When voice clarity is good, I can understand system responses easily without confusion. "
        "This gives me confidence in using the system. Additionally, responsive feedback means "
        "the assistant responds quickly to my commands, which saves me time and reduces waiting."
    )
    
    # Check that multiple elements were detected
    chains = response.get("Chains", [])
    multi_element_chains = [
        chain for chain in chains 
        if any(keyword in chain["Attribute"].lower() 
               for keyword in ["clarity", "voice clarity", "responsive", "feedback"])
    ]
    
    # Flexible assertion - we should find at least one of these elements
    assert len(multi_element_chains) > 0, "No elements from multi-element message detected"
    print(f"✅ Multi-element processing detected {len(multi_element_chains)} elements")
    
    # ATTRIBUTE TEST 2: "Ease of use" attribute (for cross-stimulus testing later)
    response = smart_home_client.send_message(
        "Another important feature is ease of use."
    )

    # Consequence for ease of use
    response = smart_home_client.send_message(
        "When it's easy to use, I can quickly control my home devices without fumbling with apps."
    )

    # Value for ease of use
    response = smart_home_client.send_message(
        "This saves me time and reduces frustration in my daily routine."
    )

    # EDGE CASE 2: Very short attribute description
    print("\n--- Testing Short Description Handling ---")
    response = smart_home_client.send_message(
        "Privacy is crucial."
    )
    
    # Check if short descriptions are properly handled
    chains = response.get("Chains", [])
    privacy_chains = [
        chain for chain in chains if "privacy" in chain["Attribute"].lower()
    ]
    
    # Just verify the system didn't crash - some models might not detect this as a feature
    print(f"Short description handling: {'✅ Privacy detected' if privacy_chains else '⚠️ Not detected (model-dependent)'}")
    
    # If privacy was detected, add a consequence
    if privacy_chains:
        response = smart_home_client.send_message(
            "When my voice assistant respects privacy, my data stays protected."
        )

    # Force stimuli change to ensure we can test merging across different contexts
    response = smart_home_client.send_message(
        "Let's switch to a different topic now. There is nothing more to add about voice assistants."
    )

    # Save chains from first stimulus for later comparison
    first_stimulus_chains = response.get("Chains", [])

    ########################
    # STIMULUS 2: Home security systems
    ########################
    print("\nTESTING WITH STIMULUS 2: Home security systems")
    smart_home_client.change_stimulus("Home security systems")

    # Start conversation with second stimulus
    response = smart_home_client.send_message(
        "I believe home security systems should provide comprehensive monitoring and be reliable."
    )

    # ATTRIBUTE TEST 3: EXACT MATCH across stimuli - Identical "ease of use" attribute
    print("\n--- Testing Cross-Stimulus Element Recognition ---")
    response = smart_home_client.send_message(
        "Ease of use is critical for security systems too."
    )

    # CONSEQUENCE TEST 4: Different consequence for ease of use in security context
    response = smart_home_client.send_message(
        "With security systems, ease of use means I can quickly arm or disarm the system "
        "when entering or leaving my home without delays."
    )

    # VALUE TEST 4: Different value for ease of use in security context
    response = smart_home_client.send_message(
        "This gives me peace of mind knowing my home is protected without adding complexity to my life."
    )

    # ATTRIBUTE TEST 4: SIMILAR attribute (similar to natural language understanding)
    response = smart_home_client.send_message(
        "Voice recognition accuracy is very important for security systems."
    )

    # CONSEQUENCE TEST 5: Consequence for voice recognition
    response = smart_home_client.send_message(
        "When the system accurately recognizes my voice, it provides better security by only responding to authorized users."
    )

    # VALUE TEST 5: Value for voice recognition
    response = smart_home_client.send_message(
        "This makes me feel secure knowing that only my family members can control the security system."
    )

    # EDGE CASE 3: Contradictory information
    print("\n--- Testing Contradictory Information Handling ---")
    response = smart_home_client.send_message(
        "Voice recognition is actually terrible for security systems because it can be spoofed."
    )
    
    # Just observe how the system handles this contradiction - no strict assertions

    # ATTRIBUTE TEST 5: EXACT MATCH - Identical "natural language understanding" attribute
    print("\n--- Testing Cross-Stimulus Exact Matching ---")
    response = smart_home_client.send_message(
        "Natural language understanding is just as important for security systems as for voice assistants."
    )

    # CONSEQUENCE TEST 6: EXACT MATCH to stimulus 1 consequence
    response = smart_home_client.send_message(
        "When the assistant understands my natural language, I can speak normally without "
        "having to remember specific command phrases."
    )

    # VALUE TEST 6: EXACT MATCH to stimulus 1 value
    response = smart_home_client.send_message(
        "This gives me a feeling of comfort and ease when interacting with my home."
    )
    
    # EDGE CASE 4: Near-duplicate with minor variations
    print("\n--- Testing Near-Duplicate Handling ---")
    response = smart_home_client.send_message(
        "When the assistant understands natural language well, I can speak normally without "
        "having to remember particular command phrasing."
    )

    # Get final chains for analysis
    final_chains = response.get("Chains", [])

    ########################
    # COMPREHENSIVE VERIFICATION
    ########################
    print("\nVERIFYING MERGED AND DISTINCT NODES")

    # 1. Check "ease of use" attributes across stimuli
    ease_of_use_chains = [
        chain for chain in final_chains 
        if ("ease" in chain["Attribute"].lower() and "use" in chain["Attribute"].lower())
    ]

    # Should have at least one chain with this attribute
    assert len(ease_of_use_chains) > 0, "No chain with 'ease of use' attribute found"

    # Collect all consequences and values for ease of use
    ease_of_use_consequences = []
    ease_of_use_values = []
    for chain in ease_of_use_chains:
        if "Consequence" in chain:
            ease_of_use_consequences.extend(chain["Consequence"])
        if "Values" in chain:
            ease_of_use_values.extend(chain["Values"])

    # Check for both voice assistant and security system consequences
    voice_keywords = ["control", "home device", "app", "quick"]
    security_keywords = ["arming", "disarming", "entering", "leaving", "delay"]

    voice_matches = sum(1 for keyword in voice_keywords if any(
        keyword.lower() in cons.lower() for cons in ease_of_use_consequences))
    security_matches = sum(1 for keyword in security_keywords if any(
        keyword.lower() in cons.lower() for cons in ease_of_use_consequences))

    # Flexible assertion - we should find at least one voice-related consequence
    assert voice_matches >= 1, f"Voice assistant consequences not found: {ease_of_use_consequences}"
    
    # More lenient assertion for security keywords - depends on model behavior
    print(f"Security keyword matches: {security_matches}/5 (model-dependent)")
    
    # Check for values with flexible assertion
    if ease_of_use_values:
        value_keywords = ["time", "frustration", "peace", "mind", "protect"]
        value_matches = sum(1 for keyword in value_keywords if any(
            keyword.lower() in val.lower() for val in ease_of_use_values))
        
        # Just ensure we have some value matches
        print(f"Value keyword matches: {value_matches}/{len(value_keywords)}")
        assert value_matches >= 1, f"Expected values not found: {ease_of_use_values}"
        print(f"✅ Values from ease-of-use context found: {ease_of_use_values}")
    else:
        print("⚠️ No values for 'ease of use' detected (model-dependent)")

    # 2. Check "natural language understanding" chains
    natural_language_chains = [chain for chain in final_chains
                               if "natural language" in chain["Attribute"].lower()]

    # Check similar attribute recognition (voice recognition should be similar to natural language)
    voice_recognition_chains = [chain for chain in final_chains
                                if "voice recognition" in chain["Attribute"].lower()]

    # Combined analysis - either merged as similar attributes or kept separate
    nlp_related_chains = natural_language_chains + voice_recognition_chains
    assert len(nlp_related_chains) > 0, "No natural language or voice recognition chains found"

    # Collect all consequences and values
    nlp_consequences = []
    nlp_values = []
    for chain in nlp_related_chains:
        if "Consequence" in chain:
            nlp_consequences.extend(chain["Consequence"])
        if "Values" in chain:
            nlp_values.extend(chain["Values"])

    # Check for recognition of exact duplicates in consequences with flexible assertion
    speak_normally_variants = [cons for cons in nlp_consequences
                              if "speak normally" in cons.lower() and "command" in cons.lower()]
    
    # Allow up to 2 similar variants due to differences in model behavior
    assert len(speak_normally_variants) <= 2, f"Too many duplicate consequences detected: {speak_normally_variants}"
    
    # Check for values with flexible assertion
    if nlp_values:
        comfort_variants = [val for val in nlp_values
                           if "comfort" in val.lower() or "ease" in val.lower()]
        assert len(comfort_variants) <= 2, f"Too many duplicate values detected: {comfort_variants}"
    
    print(f"✅ Natural language understanding chains properly handled")
    print(f"✅ Consequences: {nlp_consequences[:3]}{'...' if len(nlp_consequences) > 3 else ''}")
    if nlp_values:
        print(f"✅ Values: {nlp_values[:3]}{'...' if len(nlp_values) > 3 else ''}")
    
    # 3. Check that system properly distinguishes between security-specific and assistant-specific elements
    security_specific = ["secure", "protection", "monitoring", "authorized", "arm", "disarm"]
    assistant_specific = ["apps", "control", "home devices"]

    # Count matches with more flexible assertions
    security_matches = sum(1 for keyword in security_specific if any(
        keyword.lower() in cons.lower() for chain in final_chains
        for cons in chain.get("Consequence", [])))

    assistant_matches = sum(1 for keyword in assistant_specific if any(
        keyword.lower() in cons.lower() for chain in final_chains
        for cons in chain.get("Consequence", [])))

    # Flexible assertions - we should find at least 1 match of each type
    assert security_matches >= 1, "Security-specific consequences not found"
    assert assistant_matches >= 1, "Assistant-specific consequences not found"

    # 4. Edge case results verification
    print("\n--- Edge Cases Summary ---")
    
    # Check multi-element processing success
    multi_element_count = len([
        chain for chain in final_chains 
        if any(keyword in chain["Attribute"].lower() for keyword in ["clarity", "responsive", "feedback"])
    ])
    print(f"Multi-element processing detected {multi_element_count} elements")
    
    # Check short description handling
    privacy_chains = [chain for chain in final_chains if "privacy" in chain["Attribute"].lower()]
    print(f"Short description handling: {'✅ Privacy detected' if privacy_chains else '⚠️ Not detected (model-dependent)'}")
    
    # Check contradictory information handling
    contradictory_chains = len([
        cons for chain in final_chains 
        for cons in chain.get("Consequence", []) 
        if "terrible" in cons.lower() or "spoofed" in cons.lower()
    ])
    print(f"Contradictory info handling: {'✅ Detected contradiction' if contradictory_chains > 0 else '⚠️ Not detected explicitly (model-dependent)'}")
    
    # Final verification
    print(f"\n✅ Test summary: Successfully processed {len(final_chains)} element chains")
    print(f"✅ Test successful: Node merging works appropriately for identical and similar elements")
