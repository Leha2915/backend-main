"""
Templates for element analysis in the interview process.
Used for analyzing responses, checking ideas, and determining node similarity.
"""

ELEMENT_ANALYSIS_TEMPLATES = {
    # ── ACV-Analysis ────────────
"node_type_analysis": """
# LADDERING INTERVIEW ELEMENT ANALYZER

You are an expert in means-end chain theory and the laddering interview method, specifically skilled at recognizing elements in participant responses.
Your task is to analyze the user's message and identify ALL distinct elements and their relationships.

## INTERVIEW CONTEXT
- Topic: {topic}
- Stimulus: {stimulus}
- Current interview path (from root to active node): {interview}
- Current active node: {active_node_info}     # textual summary of the active node
- Current active node label: {active_node_label}
- Last question asked: "{last_question}"

## USER MESSAGE TO ANALYZE
"{message}"

## DEFINITIONS & SUBCATEGORIES (use these to classify):
- ATTRIBUTE (A): System characteristics or triggering features that users can directly perceive or experience.
  - Concrete attributes: Specific, identifiable system features or properties
    Examples: 'interface elements', 'functions', 'capabilities', 'technical features'
  - Abstract attributes: Non-physical but observable characteristics
    Examples: 'ease of use', 'responsiveness', 'accessibility', 'design style'
    
- CONSEQUENCE (C): Direct functional or emotional outcomes that result from using specific attributes.
  - Functional consequences: Practical outcomes and direct benefits
    Examples: 'faster task completion', 'fewer mistakes', 'better organization', 'easier access'
  - Experiential consequences: Personal experiences and feelings during use
    Examples: 'feels more in control', 'less frustration', 'more confident', 'better workflow'

- VALUE (V): is an enduring belief that a specific mode of conductor end-state of existence is personally or socially
  preferable to an opposite or converse mode of conduct or end-state of existence. So they are fundamental end-states or goals that cannot be further explained through deeper questioning.
  These represent the ultimate "why" behind user preferences and behaviors.
  - Value categories (examples from literature):
    - SOCIAL (terminal, interpersonal): e.g.:"Family security", "True friendship", "Freedom", "Connection to others"
    - MORAL (instrumental, interpersonal): e.g.:"Forgiving", "Helpful", "Honest", "Responsible", "Making a difference"
    - PERSONAL (terminal, intrapersonal): e.g.:"A comfortable life", "Happiness", "Wisdom", "Self-respect", "Peace of mind", "Balance in life"
    - COMPETENCY (instrumental, intrapersonal): e.g.:"Ambitious", "Capable", "Independent", "Logical", "Feeling accomplished"

- IRRELEVANT: Messages that don't contribute meaningful content to the interview.
  Examples: greetings (e.g.: 'hi', 'hello', 'hey'), very short responses without topic relevance (e.g.: 'ok', 'yes', 'no'), 
  off-topic comments, or responses that don't relate to the interview topic.

## PROCESS RULES
1. First, read the user message carefully and compare it to the active node and interview context
2. Identify ALL distinct elements (attributes, consequences, values) mentioned in the message
3. For each element, determine if it's truly new or just an elaboration on the current active node
4. Determine if the message contains multiple elements
5. For multiple elements, analyze if there are causal relationships between them (A→C, C→C, C→V)

## CLASSIFICATION PRIORITY BASED ON ACTIVE NODE:
- Active node type is {active_node_label} - use this to guide your classification
- If active node label is IDEA: Classify ambiguous elements preferentially as ATTRIBUTES (beginning of the means-end chain)
- If active node label is ATTRIBUTE [A]: Classify ambiguous elements preferentially as CONSEQUENCES (natural progression)
- If active node label is CONSEQUENCE [C]: Classify highly ambiguous elements preferentially as VALUES
- Only override these preferences when classification is clearly indicated by content

## HINTS ON CLASSIFICATION:
- Any statement mentioning how something makes the user FEEL is likely a VALUE
- VALUES are about emotional states, fundamental human needs and life goals
- VALUES are often the "final destination" in a chain of reasoning - they explain the ultimate "why"
- Personal importance or emotional impact often indicates VALUES
- Statements about what a function specifically offers are usually ATTRIBUTES
- Statements about immediate benefits are usually CONSEQUENCES

## ELEMENT RELATIONSHIP DETECTION
For multiple elements, carefully analyze causal relationships where the FIRST element CAUSES or LEADS TO the SECOND element:
- A→C relationship: When an attribute CAUSES a consequence
  Example: "It's lightweight [A] which allows me to carry it everywhere [C]"
  (Here, "lightweight" is the CAUSE that enables "carry it everywhere" as the EFFECT)
  BUT note grammatical difference: "It allows me to carry it everywhere [C], which is possible because it's lightweight [A]". So, you have to be careful with the order of the elements.

- C→C relationship: When one consequence CAUSES another consequence, potentially forming complex chains of causality
  Complex example with three connected consequences: "The automatic updates [C1] enable faster bug fixing [C2], which leads to improved system reliability [C3]."
  (Here we have a causal chain where C1→C2→C3, with each consequence causing the next)
  
  Complex grammatical example: "The app provides me better work quality [C3], because it requires less time for corrections [C2], which is made possible by its intelligent suggestions [C1]."
  (Here, despite the grammatical order being C3←C2←C1, the actual causal relationships are C1→C2→C3)
  
  The complexity increases with more elements, requiring careful analysis of the entire grammatical structure to determine the true causal flow. For longer chains, often the last element is a value (V), e.g. C1→C2→C3→V.

- C→V relationship: When a consequence CAUSES or fulfills a deeper value
  Example: "It keeps my data secure [C] which gives me peace of mind [V]"
  (Here, "keeps data secure" is the CAUSE that leads to "peace of mind" as the EFFECT)
  BUT note grammatical difference: "It gives me peace of mind [V],by keeping my data secure [C]"

IMPORTANT: In causal relationships (→), what appears on the LEFT SIDE of the arrow CAUSES what appears on the RIGHT SIDE. The arrow points from CAUSE to EFFECT. However, natural language often presents 
these relationships in complex grammatical structures where causes and effects might appear in reverse order or be embedded in complex sentences.
ALWAYS ANALYZE THE ENTIRE SENTENCE AND ITS GRAMMATICAL STRUCTURE before determining causal relationships. This is particularly critical when dealing with multiple elements (3 or more) where a chain of 
causality might be present but expressed in non-linear ways. Pay close attention to causal connectors (because, since, as, due to, therefore, thus, etc.) that signal the true direction of causality regardless of word order.

## SPECIAL INSTRUCTIONS:
- ONLY identify elements that are EXPLICITLY mentioned by the user
- DO NOT infer consequences or values unless the user clearly states them
- An element should be marked as NEW (is_new_element: true) unless it is EXACTLY the same concept already expressed in the active node
- When a user mentions something that's related to the active node but expresses a distinct benefit, outcome, or feature, it should be marked as NEW
- Even if a consequence refers to the active node, it should be marked as NEW if it represents a distinct outcome or result
- When the active node is an Attribute (A) and the user mentions a Consequence (C), the C MUST be marked as NEW (is_new_element: true)
- When the active node is a Consequence (C) and the user mentions a Value (V), the V MUST be marked as NEW (is_new_element: true)
- When detecting a causal relationship, ensure both elements are distinct (not the same concept rephrased)
- Consider the context of the last question: "{last_question}" and the current interview path: {interview}

## EXAMPLE SCENARIOS

### Example 1 - Related but new element:
Active node: "Automated bill payment" (C)
User message: "This prevents late fees and reduces my financial stress"
Correct analysis: "Prevents late fees" is a NEW consequence and implies the NEW consequence "Reduces financial stress" (is_new_element: true) - "Prevents late fees" is related to but distinct from "automated bill payment"

### Example 2 - Value from consequence:
Active node: "Regular data backups" (C)
User message: "This gives me peace of mind knowing my important files are always safe"
Correct analysis: "Peace of mind" is a NEW value (is_new_element: true) - it's the emotional benefit from the backup consequence

### Example 3 - Elaboration (not new):
Active node: "Waterproof design" (A)
User message: "Yes, the waterproof capability is definitely important"
Correct analysis: This is NOT a new element (is_new_element: false) - it's just repeating/agreeing with the active node

## RESPOND WITH THIS JSON STRUCTURE
{{
  "contains_multiple_elements": true|false,
  "elements": [
    {{
      "category": "ATTRIBUTE|CONSEQUENCE|VALUE|IRRELEVANT",
      "summary": "Brief 3-5 word summary",
      "text_segment": "The exact portion of text containing this element",
      "is_new_element": true|false,
    }},
    // Additional elements if present
  ],
  "causal_relationships": [
    {{
      "source_element_index": 0,  // Index in the elements array
      "target_element_index": 1,  // Index in the elements array
      "relationship_type": "A→C|C→C|C→V",
      "explanation": "Brief explanation of how the source element CAUSES the target element"
    }},
    // Additional relationships if present
  ]
}}

## CRITICAL FORMATTING INSTRUCTIONS:
1. Return ONLY the JSON structure above - DO NOT include any additional text, explanations, or thoughts outside this structure
2. If you need to think through your analysis, do so before constructing the final JSON
3. If you wish to revise your initial assessment, make all corrections within the single JSON response
4. Never include multiple JSON objects or write explanations outside the JSON structure

IMPORTANT NOTES:
- If the message is just a greeting,  or off-topic, classify it as IRRELEVANT
- For IRRELEVANT messages, explain why in the summary (e.g., "greeting", "off-topic")
- Only include "causal_relationships" when you detect explicit connections between elements
- In causal relationships, always ensure the SOURCE element CAUSES the TARGET element
- Ensure all JSON fields are properly populated for each identified element

## STRICT CLASSIFICATION RULES BASED ON ACTIVE NODE TYPE
The current active node type is {active_node_label}. Follow these mandatory rules when classifying elements:

1.When ACTIVE NODE is IDEA:
   - ONLY ATTRIBUTES can be recognized and classified
   - Ignore any consequences or values mentioned by the user
   - Focus exclusively on identifying concrete or abstract attributes

2. When ACTIVE NODE is ATTRIBUTE:
   - ONLY CONSEQUENCES can be recognized and classified
   - Ignore any values or additional attributes mentioned by the user
   - Focus on identifying functional or experiential consequences that result from the active attribute

3. When ACTIVE NODE is CONSEQUENCE:
   - PRIMARY: Look for CONSEQUENCES or VALUES
   - For VALUES: 
     * MUST have a clear causal relationship with the active consequence node
     * If no causal relationship exists (C→V), the value must be IGNORED
     * The active consequence must directly lead to or fulfill the value
   - For CONSEQUENCES:
     * MUST be causally dependent on the active consequence node (C→C relationship)
     * The new consequence must be a direct result or effect of the active consequence
     * Ignore consequences that are unrelated or parallel to the active node
   - For ATTRIBUTES:
     * Can be recognized but BE VERY CONSERVATIVE
     * Only identify if explicitly and clearly stated
     * Default to ignoring attributes unless absolutely certain

4. GENERAL RESTRAINT PRINCIPLE:
   - BE CONSERVATIVE when identifying multiple elements
   - When in doubt, identify FEWER elements rather than more
   - It's better to miss a potential element than to over-identify
   - Focus on the most clear and explicit elements only
   - Avoid inferring or reading between the lines


### IMPORTANT: Strictly adhere to ALL rules above. These rules are MANDATORY.

# """,


    "idea_check": """
# IDEA CLASSIFICATION FOR LADDERING INTERVIEWS

You are an expert in laddering interviews and means-end chain theory. Your task is to analyze a user's response and determine if it contains a concrete application idea related to the given stimulus.

## CONTEXT
- Topic: {topic}
- Stimulus: {stimulus}
- Last question asked: "{last_question}"

## USER RESPONSE TO ANALYZE
"{message}"

## DEFINITIONS
- IDEA: A concrete application or specific implementation of the stimulus. It should be a practical way the user thinks the stimulus could work for them personally. It transforms a generic trigger (stimulus) into a concrete application concept.
  Examples:
  - Stimulus: "Voice-controlled assistants" → Idea: "I think voice assistants would be useful for hands-free control of my smart home devices"
  - Stimulus: "Offline playback" → Idea: "I would use offline playback to download podcasts before my commute"
  
- IRRELEVANT: Messages that don't contribute meaningful content to the interview.
  Examples: greetings (e.g.: 'hi', 'hello', 'hey'), very short responses without topic relevance (e.g.: 'ok', 'yes', 'no'), off-topic comments, or responses that don't relate to the interview topic.

## WHAT MAKES A GOOD IDEA IN LADDERING INTERVIEWS
1. It's PERSONALIZED - shows how the user would specifically use or benefit from the stimulus
2. It's CONCRETE - provides a specific implementation or application scenario
3. It's ACTIONABLE - describes a clear way the stimulus could be used
4. It's RELEVANT - directly relates to the stimulus and topic
5. It goes BEYOND just repeating the stimulus or giving general opinions

## NOT AN IDEA
- Generic opinions about the stimulus without specific applications
- Simple agreement or acknowledgment without added details
- Statements that just rephrase the stimulus without adding personal context
- Comments about features without explaining their application

## ANALYSIS INSTRUCTIONS
1. Read the user's response carefully
2. Determine if it contains a concrete application idea related to the stimulus
3. Consider if the response is meaningful to the interview or irrelevant (greeting, etc.)
4. Create a brief summary based on the following rules:
   - For IDEA responses: Summarize the specific application or implementation mentioned (3-5 words)
   - For relevant but non-IDEA responses: Still extract the key concept from the user's message (3-5 words)
   - For IRRELEVANT responses: Explain why it's irrelevant (e.g., "greeting", "off-topic")
5. Provide your final classification and reasoning

## SUMMARY CREATION GUIDANCE
- For relevant content (whether IDEA or not): Focus on extracting the core concept from the user's message
- The summary should reflect WHAT THE USER SAID, not your evaluation of it
- Example: If user says "Voice assistants help me control my home", the summary should be "home control assistance" NOT "general opinion" or "not specific enough"
- Keep summaries concise (4-6 words) but informative about the content

## RESPOND WITH THIS JSON STRUCTURE
{{
  "is_idea": true|false,
  "summary": "Brief 4-6 word summary of the user's actual message content",
  "text_segment": "The exact portion of text containing the key concept",
  "is_relevant": true|false,
  "explanation": "Brief explanation of your reasoning"
}}
""",

# ── Template that checks node merging ─────────────────────
    
    "node_similarity_check": """
# PARALLEL NODE SIMILARITY ANALYSIS

Your task is to analyze a new element from a means-end chain interview and determine if it represents the SAME concept as any of the candidate elements, despite potentially having different wording.

## NEW ELEMENT
- Element type: {node_type}
- Summary: "{new_node_summary}"
- Full context path (from element to root): 
{new_node_path}

## CANDIDATE ELEMENTS TO COMPARE WITH
{candidates_formatted}

## GUIDELINES FOR SIMILARITY ASSESSMENT
1. Focus on the core meaning and intent behind each element, not just the specific wording
2. Consider the hierarchical context - elements with similar parents may be more likely to be the same concept
3. Consider the interview topic ({topic}) and stimulus ({stimulus}) when determining similarity
4. Attributes (A) should match in their concrete characteristics
5. Consequences (C) should match in their functional benefits or outcomes 
6. Values (V) should match in their emotional significance or personal meaning

## YOUR TASK
For EACH candidate element (0 to ({num_candidates} - 1)), independently determine if it represents the same underlying concept as the new element, considering:
- Direct content similarity (meaning and intent)
- Position in the means-end chain
- Hierarchical relationships

## IMPORTANT
- Assess each candidate independently from the others
- A candidate can be similar even if its wording is completely different, as long as it conveys the same core concept
- Consider the context paths - nodes with similar parents often represent related concepts
- For each candidate, provide a clear explanation of why you believe it is or is not similar to the new element

## RESPOND WITH THIS JSON STRUCTURE
{{
  "similarity_results": [
    {{
      "candidate_id": 0,
      "should_merge": true|false,
      "explanation": "Brief explanation of your reasoning",
      "confidence_score": 0-100
    }},
    {{
      "candidate_id": 1,
      "should_merge": true|false,
      "explanation": "Brief explanation of your reasoning",
      "confidence_score": 0-100
    }},
    // Additional results for each candidate
  ]
}}

Take care to include all candidates in your json response and ensure the JSON is valid. Don't include any text outside the JSON structure.

Confidence score should reflect your certainty in the assessment (0=completely uncertain, 100=completely certain).
""",
}