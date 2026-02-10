import pytest
import requests
import sys
import os
import pathlib

# Add the root directory to the path
root_dir = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Import after sys.path modification
from tests.conftest import SMART_HOME_STIMULI


def test_multi_stimuli_single_session(smart_home_client):
    """
    Tests that a single interview session can handle multiple stimuli sequentially,
    building a continuous tree across different stimuli discussions.
    
    1. First part: Voice-controlled assistants - create a complete ACV chain
    2. Without ending session, change the stimulus to Home security systems
    3. Continue same session with new stimulus
    4. Create similar content to test cross-stimuli node merging
    5. Verify tree structure has elements from both stimuli
    """
    print("\n=== TEST: Multiple Stimuli in Single Session ===")
    
    ########################
    # PART 1: Voice-controlled assistants
    ########################
    print("\nTESTING STIMULUS 1: Voice-controlled assistants")
    
    # Start conversation
    response = smart_home_client.send_message("Hello")
    
    # Record session ID - we'll reuse this for the entire test
    session_id = smart_home_client.session_id
    print(f"Session ID: {session_id}")
    assert session_id is not None, "No session ID assigned"
    
    # Create a complete ACV chain
    response = smart_home_client.send_message(
        "I think voice assistants are great because they understand natural language."
    )
    
    response = smart_home_client.send_message(
        "When they understand natural language, I can speak normally without using specific commands."
    )
    
    response = smart_home_client.send_message(
        "This gives me a feeling of comfort and ease when controlling my home."
    )
    
    # Add another attribute
    response = smart_home_client.send_message(
        "Voice assistants also need to have good privacy features."
    )

    # Add another attribute
    response = smart_home_client.send_message(
        "end interview"
    )
    # Add another attribute
    response = smart_home_client.send_message(
        "end interview"
    )
    # Add another attribute
    response = smart_home_client.send_message(
        "end interview"
    )

    
    # Record chains from first stimulus
    voice_assistant_chains = response.get("Chains", [])
    
    ########################
    # PART 2: Home security systems - SAME SESSION
    ########################
    print("\nSWITCHING STIMULUS - SAME SESSION: Home security systems")
    
    # *** KEY DIFFERENCE: Don't reset client, just change the stimulus ***
    # Maintain the same session_id by not calling reset()
    smart_home_client.change_stimulus(SMART_HOME_STIMULI[1])
    
    # Verify session ID remains the same
    assert smart_home_client.session_id == session_id, "Session ID changed unexpectedly"
    
    # Provide a transition message to change the topic
    response = smart_home_client.send_message(
        "Now I'd like to talk about home security systems. Wird aktuell geskippt als frage"
    )

    #Idea
    response = smart_home_client.send_message(
        "Home security systems are important for protecting my family and property."
    )
    
    # Create a similar attribute to test merging
    response = smart_home_client.send_message(
        "Security systems should also have natural language understanding."
    )
    
    # Create a consequence similar to first session
    response = smart_home_client.send_message(
        "With natural language understanding, I can use simple voice commands to arm or disarm the system."
    )
    
    # Create a value similar to first session - this should potentially merge
    response = smart_home_client.send_message(
        "This gives me comfort and ease when managing home security."
    )
    
    # Create a unique attribute for security systems
    response = smart_home_client.send_message(
        "Security systems need to be reliable in emergency situations."
    )
    
    response = smart_home_client.send_message(
        "With high reliability, the system works when I need it most during emergencies."
    )
    
    response = smart_home_client.send_message(
        "This gives me peace of mind knowing my family is protected."
    )
    
    # Get final chains with both stimuli
    final_chains = response.get("Chains", [])
    
    ########################
    # VERIFICATION
    ########################
    print("\nVERIFYING MULTI-STIMULI SESSION HANDLING")
    
    # Verify there are chains for both stimuli
    print(f"Total chains in final response: {len(final_chains)}")
    
    # Look for voice assistant content
    voice_terms = ["voice", "assistant", "privacy"]
    voice_matches = sum(1 for term in voice_terms if any(
        term.lower() in chain.get("Attribute", "").lower() or
        any(term.lower() in cons.lower() for cons in chain.get("Consequence", [])) or
        any(term.lower() in val.lower() for val in chain.get("Values", []))
        for chain in final_chains
    ))
    print(f"Voice assistant terms found: {voice_matches}")
    
    # Look for security system content
    security_terms = ["security", "emergency", "reliable", "protect"]
    security_matches = sum(1 for term in security_terms if any(
        term.lower() in chain.get("Attribute", "").lower() or
        any(term.lower() in cons.lower() for cons in chain.get("Consequence", [])) or
        any(term.lower() in val.lower() for val in chain.get("Values", []))
        for chain in final_chains
    ))
    print(f"Security system terms found: {security_matches}")
    
    # Check for cross-stimuli term: "natural language"
    nlp_chains = [chain for chain in final_chains 
                 if "natural language" in chain["Attribute"].lower()]
    print(f"Natural language chains: {len(nlp_chains)}")
    
    # Verify content from both stimuli exists
    assert voice_matches > 0, "No voice assistant terms found in final chains"
    assert security_matches > 0, "No security system terms found in final chains"
    
    # The real test - if we have proper cross-stimuli merging, we should ideally have exactly one
    # natural language understanding attribute chain that contains consequences from both domains
    if len(nlp_chains) == 1:
        nlp_chain = nlp_chains[0]
        cons_count = len(nlp_chain.get("Consequence", []))
        print(f"✅ MERGING SUCCESSFUL: Single natural language chain with {cons_count} consequences")
        
        # Check if the chain has consequences for both voice commands and security commands
        cons_text = " ".join(nlp_chain.get("Consequence", [])).lower()
        has_voice = any(term in cons_text for term in ["speak", "command", "voice"])
        has_security = any(term in cons_text for term in ["security", "arm", "disarm"])
        
        if has_voice and has_security:
            print("✅ CROSS-STIMULI MERGING: Chain contains consequences for both voice and security!")
    else:
        print(f"Multiple ({len(nlp_chains)}) natural language chains found - cross-stimuli merging might be limited")
    
    print("\n✅ Cross-stimuli test completed - tree contains elements from both stimuli")