import pytest
import time
import requests





def test_multi_attributes_in_one_response(interview_client):
    """
    Test für den Fall, dass der Benutzer mehrere Attribute in einer Antwort nennt.

    Das System sollte:
    1. Alle genannten Attribute erkennen
    2. Für jedes Attribut eine eigene Chain anlegen
    3. Mit Fragen zu den erkannten Attributen fortfahren
    """
    print("\n=== TEST: Mehrere Attribute in einer Antwort ===")

    # Schritt 1: Begrüßung senden
    response = interview_client.send_message("Hello")

    # Schritt 2: Benutzer antwortet auf die IDEA-Frage
    response = interview_client.send_message(
        "I think offline playback should allow me to save my favorite music and playlists to my device. "
        "It should work seamlessly in the background and automatically sync when I'm back online."
    )

    # Schritt 3: Mit einer Antwort reagieren, die mehrere Attribute enthält
    multi_attribute_response = (
        "I think there are several important features for offline playback: "
        "First, automatic playlist downloads before trips based on my listening habits. "
        "Second, quality settings to control how much storage space is used. "
        "And third, the ability to share offline playlists with friends when we're both offline."
    )

    response = interview_client.send_message(multi_attribute_response)

    # Prüfen, ob mehrere Attribute erkannt wurden
    chains = response.get("Chains", [])
    assert len(
        chains) >= 3, f"Erwartete mindestens 3 Chains, aber nur {len(chains)} gefunden"

    # Attribute-Texte extrahieren
    attributes = [chain["Attribute"] for chain in chains]
    print(f"\n✓ Erkannte Attribute: {attributes}")

    # Prüfen, ob die wichtigsten Konzepte erkannt wurden
    important_keywords = ["download", "automatic",
                          "quality", "storage", "share", "offline"]

    # Mindestens 3 der Keywords sollten in den erkannten Attributen vorkommen
    keyword_matches = sum(1 for keyword in important_keywords if any(
        keyword.lower() in attr.lower() for attr in attributes))
    assert keyword_matches >= 3, f"Zu wenige wichtige Konzepte erkannt: {keyword_matches}/6"

    # Schritt 4: Zwei Konsequenz für eines der Attribute angeben
    response = interview_client.send_message(
        "The automatic playlist downloads before trips means I never have to worry about "
        "remembering to download music before traveling. It also ensures I always have fresh content."
    )

    # Prüfen, ob die Konsequenzen zur richtigen Chain hinzugefügt wurden
    updated_chains = response.get("Chains", [])

    # Mindestens eine Chain sollte Konsequenzen haben
    chains_with_consequences = [chain for chain in updated_chains if chain.get(
        "Consequence") and len(chain["Consequence"]) > 0]
    assert len(
        chains_with_consequences) > 0, "Keine Chain mit Konsequenzen gefunden"

    # Schritt 5: Mehrere Werte in einer Antwort angeben
    multi_value_response = (
        "Having these features makes me feel secure knowing I'll always have my music. "
        "It gives me a sense of freedom to enjoy music anywhere. "
        "And it saves me time because I don't have to manually prepare everything."
    )

    response = interview_client.send_message(multi_value_response)

    # Prüfen, ob Werte erkannt wurden
    final_chains = response.get("Chains", [])
    chains_with_values = [chain for chain in final_chains if chain.get(
        "Values") and len(chain["Values"]) > 0]

    assert len(chains_with_values) > 0, "Keine Chain mit Values gefunden"

    # Werte aus den Chains extrahieren
    all_values = []
    for chain in chains_with_values:
        all_values.extend(chain["Values"])

    # Prüfen, ob wichtige Werte-Keywords erkannt wurden
    value_keywords = ["secure", "security", "freedom",
                      "time", "efficiency", "peace", "mind"]
    value_matches = sum(1 for keyword in value_keywords if any(
        keyword.lower() in value.lower() for value in all_values))

    assert value_matches >= 2, f"Zu wenige wichtige Werte erkannt: {value_matches}/7"

    print(
        f"\n✅ Test erfolgreich: {len(chains)} Chains mit mehreren Attributen erkannt")
    print(f"✅ {len(chains_with_consequences)} Chains mit Konsequenzen")
    print(f"✅ {len(chains_with_values)} Chains mit Werten")
    print(f"✅ Erkannte Werte: {all_values}")


def test_multiple_consequences_in_one_response(interview_client):
    """
    Test für den Fall, dass der Benutzer mehrere Konsequenzen zu einem Attribut in einer Antwort nennt.
    """
    print("\n=== TEST: Mehrere Konsequenzen in einer Antwort ===")

    # Schritt 1 Erste Nachricht senden
    response = interview_client.send_message("Hi")

    # Schritt 2: Benutzer antwortet auf die IDEA-Frage
    response = interview_client.send_message(
        "I think offline playback should allow me to save my favorite music and playlists to my device. "
        "It should work seamlessly in the background and automatically sync when I'm back online."
    )

    # Schritt 3: Eine klare Antwort mit einem Attribut
    response = interview_client.send_message(
        "The most important feature is automatic smart downloads")

    # Schritt 4: Mehrere Konsequenzen in einer Antwort angeben
    multi_consequence_response = (
        "Smart downloads have several benefits: I save battery life because I don't need to search "
        "for music while on the go. I also save mobile data since everything is already downloaded. "
        "And I can listen to higher quality audio without buffering issues."
    )

    response = interview_client.send_message(multi_consequence_response)

    # Prüfen, ob mehrere Konsequenzen erkannt wurden
    chains = response.get("Chains", [])
    assert len(chains) > 0, "Keine Chains gefunden"

    # Die erste Chain sollte die mit "smart downloads" sein
    relevant_chains = [
        chain for chain in chains if "download" in chain["Attribute"].lower()]
    assert len(
        relevant_chains) > 0, "Keine Chain mit 'download' im Attribut gefunden"

    # Diese Chain sollte mehrere Konsequenzen haben
    main_chain = relevant_chains[0]
    assert "Consequence" in main_chain, "Keine Consequences in der relevanten Chain"
    assert len(main_chain["Consequence"]
               ) >= 2, f"Zu wenige Consequences erkannt: {len(main_chain['Consequence'])}"

    # Prüfen, ob wichtige Konsequenz-Keywords erkannt wurden
    consequence_keywords = ["battery", "data", "quality", "buffering"]
    consequences = main_chain["Consequence"]
    consequence_matches = sum(1 for keyword in consequence_keywords if any(
        keyword.lower() in c.lower() for c in consequences))

    assert consequence_matches >= 2, f"Zu wenige wichtige Konsequenzen erkannt: {consequence_matches}/4"

    print(
        f"\n✅ Test erfolgreich: {len(main_chain['Consequence'])} Konsequenzen in einer Chain erkannt")
    print(f"✅ Erkannte Konsequenzen: {main_chain['Consequence']}")
