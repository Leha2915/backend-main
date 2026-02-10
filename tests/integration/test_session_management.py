import pytest

def test_session_persistence(interview_client): # Fordere die Fixture hier an
    """Testet, ob die Session über mehrere Anfragen bestehen bleibt"""
    # ÄNDERUNG: Manuelle Erstellung entfernen
    # client = TestInterviewClient()
    
    # Erste Anfrage
    response1 = interview_client.send_message("Hi there")
    
    # Session-ID nach erster Anfrage speichern
    first_session_id = interview_client.session_id
    assert first_session_id, "Keine Session-ID nach erster Anfrage erhalten"
    
    # Zweite Anfrage
    response2 = interview_client.send_message("I like being able to listen to music when I have no internet")
    second_session_id = interview_client.session_id
    
    # Prüfen, ob die Session-ID gleich bleibt
    assert first_session_id == second_session_id, "Session-ID hat sich zwischen Anfragen geändert"
    
    print("\n✅ Test erfolgreich: Session-Persistenz funktioniert")