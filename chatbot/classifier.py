import json
import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INTENTS_PATH = os.path.join(BASE_DIR, "intents.json")


def load_intents():
    """Load training examples and their intent labels."""
    with open(INTENTS_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    texts = []
    labels = []

    for intent, examples in data["intents"].items():
        for example in examples:
            texts.append(example)
            labels.append(intent)

    return texts, labels


def train_classifier():
    """Train the intent classifier."""
    texts, labels = load_intents()

    classifier = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2)
            )
        ),
        (
            "classifier",
            LogisticRegression(
                max_iter=1000
            )
        )
    ])

    classifier.fit(texts, labels)

    return classifier


def predict_intent(classifier, user_message):
    """Predict the intent of a user message."""
    return classifier.predict([user_message])[0]


def predict_intent_with_confidence(classifier, user_message):
    """
    Predict the intent of a user message along with the model's confidence
    (max class probability). Used by the app to decide whether the
    TF-IDF/logistic-regression intent match is reliable enough to answer
    directly, or whether the request should be handed off to the Gemini
    fallback instead.
    """
    probabilities = classifier.predict_proba([user_message])[0]
    classes = classifier.classes_
    best_index = probabilities.argmax()
    return classes[best_index], float(probabilities[best_index])


if __name__ == "__main__":

    classifier = train_classifier()

    print("\nSmart Agri Intent Classifier")
    print("=" * 40)
    print("Type 'exit' to stop.\n")

    while True:

        user_message = input("You: ").strip()

        if user_message.lower() == "exit":
            break

        intent = predict_intent(classifier, user_message)

        print(f"Intent: {intent}\n")