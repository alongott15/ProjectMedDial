from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class RemediLabelDetail(BaseModel):
    label_type: Literal["intent", "action"]
    type_name: str  # E.g., "Informing", "Recommend", "Diagnosis"
    slot: str       # E.g., "Symptom", "Time", "Medicine", "Disease"
    value: str      # The textual value from the utterance, e.g., "coughing all night", "ten days"
    # sub_sentence_text: Optional[str] = None # Optional: The exact part of utterance this label refers to

class RemediAnnotatedTurn(BaseModel):
    turn_id: int
    role: str  # "Doctor" or "Patient"
    utterance_text: str
    remedi_labels: List[RemediLabelDetail] = Field(default_factory=list)

# New model for the output JSON structure
class DialogueAnnotationOutput(BaseModel):
    source_row_id: Optional[int] = None
    source_subject_id: Optional[int] = None
    source_hadm_id: Optional[int] = None
    remedi_style_dialogue_annotations: List[RemediAnnotatedTurn] = Field(default_factory=list)