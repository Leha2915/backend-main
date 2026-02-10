import pytest
import requests
import sys
import os
import pathlib
import re
from typing import List, Dict, Any

# Add the root directory to the path
root_dir = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))


def test_queue_laddering_question_generation(interview_client):
    """
    Tests the queue_laddering template's question generation capabilities across different stages
    of the interview process. Verifies that:

    1. The system generates appropriate questions for each interview stage
    2. Questions adapt to the active node and context
    3. Different questions are generated for consecutive irrelevant responses
    4. The system handles mismatched responses (e.g., value responses when attributes are expected)
    """
    print("\n=== TEST: Queue Laddering Question Generation ===")

    # Start the conversation
    response = interview_client.send_message("Hello")

    # 1. IDEA STAGE: Provide an idea about offline playback
    print("\nSTAGE 1: Testing IDEA -> ATTRIBUTE question generation")
    response = interview_client.send_message(
        "I think offline playback is really important for music streaming apps."
    )

    # Verify we're now asking for attributes with correct code
    assert response["Next"]["AskingIntervieweeFor"] == "A1.1", \
        f"Expected to be asking for A1.1, got {response['Next']['AskingIntervieweeFor']}"

    attribute_question = response["Next"]["NextQuestion"]
    print(f"Attribute question: {attribute_question}")

    # 2. ATTRIBUTE STAGE: Provide an attribute
    print("\nSTAGE 2: Testing ATTRIBUTE -> CONSEQUENCE question generation")
    response = interview_client.send_message(
        "The most important feature is automatic playlist downloads before trips."
    )

    # Verify we're now asking for consequences with correct code
    assert response["Next"]["AskingIntervieweeFor"] == "C1.1", \
        f"Expected to be asking for C1.1, got {response['Next']['AskingIntervieweeFor']}"

    consequence_question = response["Next"]["NextQuestion"]
    print(f"Consequence question: {consequence_question}")

    # 3. CONSEQUENCE STAGE: Provide a consequence
    print("\nSTAGE 3: Testing CONSEQUENCE -> CONSEQUENCE_OR_VALUE question generation")
    response = interview_client.send_message(
        "With automatic downloads, I never have to worry about remembering to download music before traveling."
    )

    # Verify we're now asking for consequences or values with correct codes
    assert response["Next"]["AskingIntervieweeFor"] in ["CV1.1", "CCV1.1"], \
        f"Expected to be asking for CV1.1 or CCV1.1, got {response['Next']['AskingIntervieweeFor']}"

    c_or_v_question = response["Next"]["NextQuestion"]
    print(f"Consequence or Value question: {c_or_v_question}")


    # 4. TEST IRRELEVANT MESSAGES: Send multiple irrelevant messages and verify different questions
    print("\nSTAGE 4: Testing multiple irrelevant message handling")

    irrelevant_messages = ["haha", "whatever", "hmm", "lol"]
    prev_questions = [c_or_v_question]

    for i, msg in enumerate(irrelevant_messages):
        print(f"\nSending irrelevant message #{i+1}: '{msg}'")
        response = interview_client.send_message(msg)

        new_question = response["Next"]["NextQuestion"]
        print(f"New question after irrelevant message: {new_question}")

        # Verify questions are different from previous ones
        for prev_q in prev_questions:
            similarity = calculate_question_similarity(prev_q, new_question)
            assert similarity < 0.7, f"Questions too similar ({similarity}): '{prev_q}' vs '{new_question}'"

        prev_questions.append(new_question)

    print("✅ System generated different questions for irrelevant messages")

    # Continue with a valid consequence to move on
    response = interview_client.send_message(
        "The automatic downloads save me mobile data since I don't need to stream music."
    )

    # Verify we get a value from this consequence
    response = interview_client.send_message(
        "This makes me feel more independent and in control of my music experience."
    )

    # Check if values are recognized
    chains = response.get("Chains", [])
    has_values = any("Values" in chain and len(
        chain["Values"]) > 0 for chain in chains)
    assert has_values, "System did not recognize the provided value"

    print("✅ System correctly processed the value response")

    print("\n✅ TEST COMPLETE: Queue Laddering template successfully generates appropriate questions")


def test_persistent_idea_node_with_value_responses(interview_client):
    """
    Tests how the system handles when a user stays on an IDEA node but keeps providing VALUE responses.
    The system should recognize the mismatch and adapt its questioning strategy.
    """
    print("\n=== TEST: Persistent IDEA Node with VALUE Responses ===")

    # Part 1: Start conversation
    response = interview_client.send_message("Hello")

    # Part 2: Provide an IDEA response to set the active node
    response = interview_client.send_message(
        "I think offline playback is really important for music streaming apps."
    )

    # Verify we're in the asking_for_attributes stage
    assert "AskingIntervieweeFor" in response["Next"], "Missing AskingIntervieweeFor field"
    expected_stage = "A1.1"
    assert response["Next"]["AskingIntervieweeFor"] == expected_stage, \
        f"Expected to be asking for {expected_stage}, got {response['Next']['AskingIntervieweeFor']}"

    # Record the first question
    first_question = response["Next"]["NextQuestion"]

    # Part 3: Provide 3 consecutive VALUE responses when attributes are expected
    value_responses = [
        "It gives me a sense of freedom to enjoy music anywhere I want.",
        "Having offline music makes me feel independent from internet constraints.",
        "It provides me with security knowing my entertainment isn't dependent on connectivity."
    ]

    previous_questions = [first_question]
    value_chains_count = 0

    for i, value_msg in enumerate(value_responses):
        print(
            f"\n🔍 Sending VALUE response #{i+1} when attributes are expected: '{value_msg}'")
        response = interview_client.send_message(value_msg)

        # Extract the new question
        new_question = response["Next"]["NextQuestion"]
        new_asking_for = response["Next"]["AskingIntervieweeFor"]
        print(f"New question: {new_question}")
        print(f"Now asking for: {new_asking_for}")

        # Verify it's different from the previous questions
        for prev_q in previous_questions:
            similarity = calculate_question_similarity(prev_q, new_question)
            assert similarity < 0.7, f"Question too similar to previous one: {similarity}"

        # Add to previous questions for future comparison
        previous_questions.append(new_question)

        # Check for evidence of adaptation in the question wording - should become more specific
        # after receiving multiple value responses but no attributes
        adaptation_keywords = ["feature", "characteristic", "aspect", "specifically",
                               "concrete", "particular", "exact", "precise"]
        has_adaptation_keywords = any(
            keyword in new_question.lower() for keyword in adaptation_keywords)

        # After the first value response, the system should show increasing signs of adaptation
        if i > 0:
            assert has_adaptation_keywords, \
                f"System not showing adaptation in questioning strategy: '{new_question}'"

        # Check if values are being recognized in chains
        chains = response.get("Chains", [])

        # Count chains with values
        current_value_chains = sum(
            1 for chain in chains if "Values" in chain and len(chain["Values"]) > 0)
        if current_value_chains > value_chains_count:
            print(
                f"✅ Found {current_value_chains} chains with values (was: {value_chains_count})")
            value_chains_count = current_value_chains

        # Print chain information for debugging
        if chains:
            print("\nCurrent chains:")
            for j, chain in enumerate(chains):
                print(f"Chain {j+1}:")
                print(f"  Attribute: {chain.get('Attribute', 'None')}")
                if "Consequence" in chain:
                    print(f"  Consequences: {chain.get('Consequence', [])}")
                if "Values" in chain:
                    print(f"  Values: {chain.get('Values', [])}")

    # By the third value response, we should see values in the chains
    assert value_chains_count > 0, "System did not recognize any values after 3 value responses"

    # We should still be trying to ask for attributes, despite receiving values
    assert response["Next"]["AskingIntervieweeFor"] == "A1.1", \
        f"System should still be asking for attributes, got {response['Next']['AskingIntervieweeFor']}"

    print("✅ System correctly handled persistent VALUE responses while staying focused on getting attributes")


def calculate_question_similarity(question1: str, question2: str) -> float:
    """
    Calculate similarity between two questions based on word overlap.
    Returns a value between 0 (completely different) and 1 (identical).

    This function normalizes the questions by removing punctuation and 
    converting to lowercase before comparing.
    """
    # Normalize: lowercase and remove punctuation
    def normalize(text):
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return set(text.split())

    # Get normalized word sets
    words1 = normalize(question1)
    words2 = normalize(question2)

    # Calculate Jaccard similarity
    common_words = words1.intersection(words2)
    all_words = words1.union(words2)

    if not all_words:
        return 0.0

    return len(common_words) / len(all_words)
