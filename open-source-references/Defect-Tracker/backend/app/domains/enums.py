from enum import StrEnum

class DefectStatus(StrEnum):
    OPEN = "open"
    REPAIRED = "repaired"

class IncidentSeverity(StrEnum):
    NEAR_MISS = "near_miss"
    DISCOMFORT = "soreness"
    FIRST_AID = "first_aid"
    RECORDABLE = "recordable" # OSHA recordable
    PSIF = "psif" # PSIF = Potentially Serious Injury or Fatality

class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CORRECTIVE_ACTION = "corrective_action"
    CLOSED = "closed"