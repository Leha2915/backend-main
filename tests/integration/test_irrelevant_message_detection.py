"""
Integration tests for irrelevant message detection functionality.
Tests how the system handles greetings, short responses and irrelevant messages.
"""

import pytest
import time
import logging
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test data
GREETINGS = [
    "hi",
    "hello",
    "hey there",
    "start",
    ".",
]

IRRELEVANT_MESSAGES = [
    "hmm",
    "ok",
    "whatever",
    "no idea",
    "???",
]

VALID_MESSAGES = [
    "I think offline playback is really important for music streaming apps",
    "The most important feature is automatic downloads before trips",
    "It helps me save battery life since I don't need to search for music",
]

def test_irrelevant_message_handling(interview_client):
    """
    Test that the system properly handles irrelevant messages and greetings.
    Verifies that the system recognizes these as irrelevant and asks appropriate follow-up questions.
    """
    print("\n=== TEST: Irrelevant Message Detection ===")
    
    # First establish context with a valid message
    print("\nStarting with a valid message to establish context...")
    response = interview_client.send_message(VALID_MESSAGES[0])
    initial_question = response["Next"]["NextQuestion"]
    print(f"Initial question: {initial_question}")
    
    # Test greeting handling
    print("\nTesting greeting response...")
    greeting = GREETINGS[0]
    response = interview_client.send_message(greeting)
    
    # Verify the system handled the greeting appropriately
    reformulated_question = response["Next"]["NextQuestion"]
    print(f"Response after greeting '{greeting}': {reformulated_question[:80]}...")
    
    # The system should not respond with something generic like "Tell me more"
    assert len(reformulated_question) > 20, "System response to greeting is too short"
    assert "tell me more" not in reformulated_question.lower(), "System response to greeting is too generic"
    
    # Test another irrelevant message
    print("\nTesting irrelevant message response...")
    irrelevant = IRRELEVANT_MESSAGES[0]
    response = interview_client.send_message(irrelevant)
    
    # Get the second reformulated question
    second_question = response["Next"]["NextQuestion"]
    print(f"Response after irrelevant message '{irrelevant}': {second_question[:80]}...")
    
    # Compare the reformulations - they should be different
    initial_words = set(initial_question.split()[:8])
    second_words = set(second_question.split()[:8])
    
    # Calculate similarity
    common_words = initial_words.intersection(second_words)
    similarity = len(common_words) / max(len(initial_words), len(second_words))
    
    print(f"Question similarity: {similarity:.2f}")
    assert similarity < 0.7, "Question was not sufficiently reformulated after irrelevant message"
    
    print("✅ System correctly reformulated the question after irrelevant input")


def test_multiple_irrelevant_responses(interview_client):
    """
    Test how the system handles multiple consecutive irrelevant messages.
    Verifies that the system generates different reformulations for repeated irrelevant inputs.
    """
    print("\n=== TEST: Multiple Irrelevant Response Handling ===")
    
    # Start with valid context
    print("\nEstablishing conversation context...")
    response = interview_client.send_message(VALID_MESSAGES[1])
    initial_question = response["Next"]["NextQuestion"]
    
    # Keep track of all reformulations
    questions = [initial_question]
    
    # Send multiple irrelevant messages in sequence
    print("\nSending sequence of irrelevant messages...")
    for i, message in enumerate(IRRELEVANT_MESSAGES[:3]):
        print(f"Sending irrelevant message {i+1}: '{message}'")
        response = interview_client.send_message(message)
        reformulated = response["Next"]["NextQuestion"]
        questions.append(reformulated)
        print(f"Reformulation {i+1}: {reformulated[:50]}...")
        
        # Brief pause to avoid rate limiting
        time.sleep(1)
    
    # Check that reformulations are sufficiently different from each other
    print("\nAnalyzing question reformulation diversity...")
    similarities = []
    
    for i in range(1, len(questions)):
        prev_words = set(questions[i-1].split()[:10])
        curr_words = set(questions[i].split()[:10])
        common = prev_words.intersection(curr_words)
        sim = len(common) / max(len(prev_words), len(curr_words))
        similarities.append(sim)
        print(f"Similarity between reformulations {i-1} and {i}: {sim:.2f}")
    
    # Check at least one reformulation is significantly different
    assert any(sim < 0.6 for sim in similarities), "System doesn't vary question reformulations enough"
    
    print("✅ System uses varied reformulations for multiple irrelevant messages")


def test_recovery_after_irrelevant_messages(interview_client):
    """
    Test that the system can recover and continue the interview after irrelevant messages.
    Verifies that the conversation gets back on track when valid input is provided.
    """
    print("\n=== TEST: Recovery After Irrelevant Messages ===")
    
    # Start with valid context
    print("\nEstablishing conversation context...")
    response = interview_client.send_message(VALID_MESSAGES[2])
    
    # Send a sequence of irrelevant messages
    print("\nSending irrelevant messages...")
    for message in IRRELEVANT_MESSAGES[:2]:
        print(f"Sending: '{message}'")
        response = interview_client.send_message(message)
        time.sleep(1)
    
    # Now send a valid message again
    print("\nSending valid message after irrelevant sequence...")
    valid_message = "It gives me a sense of freedom to enjoy music anywhere without worrying about my data plan"
    response = interview_client.send_message(valid_message)
    
    # Check that the response is relevant to the valid message
    next_question = response["Next"]["NextQuestion"]
    print(f"System response: {next_question[:80]}...")
    
    # The question should mention either "freedom", "music" or "data plan" - key concepts from the valid message
    assert any(keyword in next_question.lower() 
               for keyword in ["freedom", "music", "anywhere", "data"]), \
        "System did not respond appropriately to valid message after irrelevant messages"
    
    print("✅ System successfully recovered after irrelevant messages")