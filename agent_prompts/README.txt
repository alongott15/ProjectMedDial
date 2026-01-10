========================================
PROJECTMEDDIAL AGENT PROMPTS
========================================

This directory contains the complete system prompts for all agents
in the ProjectMedDial dialogue generation framework.

========================================
FILES:
========================================

1. BASE_SYSTEM_PROMPT.txt
   - Foundation prompt inherited by all LLM-based agents
   - Ensures grounded, bias-aware, conservative behavior
   - Anti-hallucination constraints

2. PatientAgent_PROMPT.txt
   - Simulates patient with light, common medical issue
   - Natural conversation with gradual symptom disclosure
   - Age-appropriate language and personality
   - Temperature: 0.6, Max tokens: 300

3. DoctorAgent_PROMPT.txt
   - Simulates primary care physician
   - Phase-based consultation approach
   - Clinical reasoning and empathy
   - Temperature: 0.5, Max tokens: 300

4. JudgeAgent_PROMPT.txt
   - Evaluates dialogue realism and groundedness
   - Binary decision: REALISTIC or UNREALISTIC
   - Numeric score: 0.0-1.0
   - Structured feedback for improvement
   - Temperature: 0.1, Max tokens: 800

5. EHRSummarizerAgent_PROMPT.txt
   - Summarizes clinical notes conservatively
   - Extracts key information for baseline
   - Used for STS comparison

6. DialogueSummarizerAgent_PROMPT.txt
   - Summarizes synthetic dialogues
   - Parallel format to EHR summaries
   - Used for STS comparison

7. PromptImprovementAgent_PROMPT.txt
   - Translates judge feedback to prompt modifications
   - Enables iterative dialogue refinement
   - Up to 3 attempts per dialogue

8. STSEvaluatorAgent (NO LLM PROMPT)
   - Embedding-based semantic similarity
   - Measures information retention
   - Complements judge evaluation

========================================
