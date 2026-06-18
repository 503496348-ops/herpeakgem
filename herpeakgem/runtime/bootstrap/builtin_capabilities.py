"""Built-in capability class paths."""

BUILTIN_CAPABILITY_CLASSES: dict[str, str] = {
    "chat": "herpeakgem.agents.chat.capability:ChatCapability",
    "deep_solve": "herpeakgem.capabilities.solve.capability:DeepSolveCapability",
    "deep_question": "herpeakgem.agents.question.capability:DeepQuestionCapability",
    "deep_research": "herpeakgem.agents.research.capability:DeepResearchCapability",
    "math_animator": "herpeakgem.agents.math_animator.capability:MathAnimatorCapability",
    "visualize": "herpeakgem.agents.visualize.capability:VisualizeCapability",
    "mastery_path": "herpeakgem.capabilities.mastery.capability:MasteryPathCapability",
}
