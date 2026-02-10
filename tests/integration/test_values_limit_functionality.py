import pytest

def test_values_limit_termination(values_limit_client_single):
    """
    Test-Szenario 1: Prüft, ob das Interview beendet wird, wenn das Value-Limit von 1 erreicht ist.
    """
    print("\n=== TEST: Values Limit Termination (Limit = 1) ===")
    
    # Verifiziere Anfangszustand
    assert values_limit_client_single.values_max == 1, "Wert sollte 1 sein"
    assert values_limit_client_single.values_count == 0, "Anfangswert sollte 0 sein"
    
    print(f"Testing with Values Limit: {values_limit_client_single.values_max}")
    
    # Interview starten
    response = values_limit_client_single.send_message("Hallo!")
    
    # IDEA angeben
    response = values_limit_client_single.send_message(
        "Ich denke, diese Funktion ist wichtig für die Werte-Limit-Tests."
    )
    
    # Attribut angeben
    response = values_limit_client_single.send_message(
        "Eine wichtige Eigenschaft ist die automatische Erkennung von Werten."
    )
    
    # Konsequenz angeben
    response = values_limit_client_single.send_message(
        "Wenn Werte automatisch erkannt werden, muss ich nicht über komplexe Analysen nachdenken."
    )
    
    # ERSTEN WERT angeben - sollte das Limit erreichen und Interview beenden
    response = values_limit_client_single.send_message(
        "Das gibt mir ein Gefühl von Effizienz und spart mentalen Aufwand."
    )
    
    # Prüfe Limits und Abschluss
    assert "ValuesCount" in response["Next"], "Response sollte ValuesCount enthalten"
    assert "ValuesMax" in response["Next"], "Response sollte ValuesMax enthalten"
    assert "ValuesReached" in response["Next"], "Response sollte ValuesReached enthalten"
    assert "CompletionReason" in response["Next"], "Response sollte CompletionReason enthalten"
    
    values_count = response["Next"]["ValuesCount"]
    values_max = response["Next"]["ValuesMax"]
    values_reached = response["Next"]["ValuesReached"]
    completion_reason = response["Next"]["CompletionReason"]
    end_of_interview = response["Next"]["EndOfInterview"]

    print(f"   Final Values Status:")
    print(f"   Count: {values_count}")
    print(f"   Max: {values_max}")
    print(f"   Reached: {values_reached}")
    print(f"   Completion Reason: {completion_reason}")
    print(f"   End of Interview: {end_of_interview}")
    
    # Überprüfe Erwartungen
    assert values_count >= 1, f"Mindestens 1 Wert erwartet, bekam {values_count}"
    assert values_max == 1, f"Max sollte 1 sein, bekam {values_max}"
    assert values_reached == True, "Werte-Limit sollte erreicht sein"
    assert completion_reason == "VALUES_LIMIT_REACHED", f"VALUES_LIMIT_REACHED erwartet, bekam {completion_reason}"
    assert end_of_interview == True, "Interview sollte beendet sein, wenn Werte-Limit erreicht ist"
    
    print("✅ Werte-Limit korrekt erreicht und Interview beendet")


def test_values_limit_disabled(values_limit_client_unlimited):
    """
    Test-Szenario 2: Prüft, ob mindestens 2 Values gefunden werden können, 
    wenn max_values auf -1 gesetzt ist (unbegrenzt).
    """
    print("\n=== TEST: Values Limit Deaktiviert (Limit = -1) ===")
    
    # Verifiziere Anfangszustand
    assert values_limit_client_unlimited.values_max == -1, "Max sollte -1 sein (unbegrenzt)"
    assert values_limit_client_unlimited.values_count == 0, "Anfangswert sollte 0 sein"
    
    # Interview starten
    response = values_limit_client_unlimited.send_message("Hallo!")
    
    # IDEA angeben
    response = values_limit_client_unlimited.send_message(
        "Ich denke, unbegrenzte Werte-Tests sind wichtig."
    )
    
    # Erste A-C-V Kette
    response = values_limit_client_unlimited.send_message(
        "Die erste wichtige Eigenschaft ist die Analysefähigkeit."
    )
    response = values_limit_client_unlimited.send_message(
        "Wenn die Analyse gut funktioniert, erhalte ich korrekte Ergebnisse."
    )
    response = values_limit_client_unlimited.send_message(
        "Das gibt mir Vertrauen in das System und Sicherheit."
    )
    
    # Prüfen, dass Interview noch nicht beendet wurde
    assert response["Next"]["EndOfInterview"] == False, "Interview sollte nach erstem Wert nicht beendet werden"
    
    # Zweite A-C-V Kette
    response = values_limit_client_unlimited.send_message(
        "Die zweite wichtige Eigenschaft ist die Geschwindigkeit."
    )
    response = values_limit_client_unlimited.send_message(
        "Wenn das System schnell ist, kann ich sofort Ergebnisse sehen."
    )
    response = values_limit_client_unlimited.send_message(
        "Das gibt mir Kontrolle und Effizienz in meinem Workflow."
    )
    
    # Werte überprüfen
    values_count = response["Next"].get("ValuesCount", 0)
    end_of_interview = response["Next"].get("EndOfInterview", False)
    
    print(f"📊 Status nach zwei Values:")
    print(f"   Count: {values_count}")
    print(f"   End of Interview: {end_of_interview}")
    
    # Überprüfe Erwartungen
    assert values_count >= 2, f"Mindestens 2 Werte erwartet, bekam {values_count}"
    assert end_of_interview == False, "Interview sollte nicht beendet sein (Unbegrenztes Limit)"
    
    print("✅ Unbegrenztes Werte-Limit korrekt implementiert")