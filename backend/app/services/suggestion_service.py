import random


def build_feedback(emotion: str, confidence: float) -> tuple[str, str, float]:
    emotion_key = emotion.lower()
    positive_templates = [
        "You are doing better than you think. Keep one small positive action going today.",
        "Your current state is valid. A short mindful break can shift your energy quickly.",
        "Progress is built from small moments. Keep going, one calm breath at a time.",
    ]

    tips = {
        "sad": "Try a 5-minute walk, hydration, and a message to someone you trust.",
        "angry": "Pause for box breathing: inhale 4, hold 4, exhale 4, hold 4 for 2 minutes.",
        "fear": "Ground with the 5-4-3-2-1 method and reduce screen noise for 10 minutes.",
    }

    suggestion = tips.get(emotion_key, "Keep a balanced routine: sleep, movement, and social check-ins.")
    message = random.choice(positive_templates)
    base = {"happy": 85, "neutral": 72, "surprise": 74, "sad": 46, "angry": 38, "fear": 42, "disgust": 40}
    wellness_score = max(5.0, min(98.0, base.get(emotion_key, 65) + (confidence - 0.5) * 18))
    return message, suggestion, wellness_score