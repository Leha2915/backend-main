import pytest

def test_complete_interview_flow(interview_client):
    """Führt einen vollständigen Laddering-Dialog durch"""
    client = interview_client
    
    # Schritt 1: Startgespräch
    response = client.send_message("Hey")
    
    # Schritt 2: Benutzer antwortet auf die IDEA-Frage
    response = client.send_message(
        "I think offline playback should allow me to save my favorite music and playlists to my device. "
        "It should work seamlessly in the background and automatically sync when I'm back online."
    )
    
    # Schritt 3: Spezifisches Attribut nennen
    response = client.send_message(
        "The most important feature is downloading my playlists completely for offline listening while traveling"
    )
    
    # Schritt 4: Konsequenz nennen
    response = client.send_message(
        "When I'm on a flight or in areas with poor reception, I can still enjoy my music without interruptions"
    )
    
    # Schritt 5: weitere Konsequenzen nennen
    response = client.send_message(
        "It gives me a sense of control over my entertainment options, no matter where I am"
    )

    # schritt 6: wert nennen
    final_response = client.send_message(
        "This feature enhances my overall experience and satisfaction with the service and makes it more enjoyable."
    )

    # Prüfen, ob der vollständige Workflow erfolgreich durchlaufen wurde
    chains = final_response.get("Chains", [])
    
    assert len(chains) > 0, "Keine Chains erstellt"
    
    # Mindestens eine vollständige Chain mit A, C und V sollte existieren
    complete_chains = [
        chain for chain in chains
        if (chain.get("Attribute") and 
            chain.get("Consequence") and len(chain["Consequence"]) > 0 and
            chain.get("Values") and len(chain["Values"]) > 0)
    ]
    
    assert len(complete_chains) > 0, "Keine vollständige ACV-Chain gefunden"
    
    print(f"\n✅ Test erfolgreich: {len(complete_chains)} vollständige ACV-Chains erstellt")