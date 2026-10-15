from context import load_latest_report
from classifier import train_classifier, predict_intent
from response_engine import generate_response


def main():

    print("\n" + "=" * 50)
    print("        🌱 SMART AGRI CHATBOT")
    print("=" * 50)

    # Load the latest Smart Agri analysis
    try:
        report = load_latest_report()
    except FileNotFoundError as error:
        print(f"\nError: {error}")
        return

    # Train intent classifier
    classifier = train_classifier()

    print(f"\nCurrent crop analysis: {report['chosen_crop']}")
    print("Ask me anything about your Smart Agri results.")
    print("Type 'exit' to close the chatbot.\n")

    while True:

        user_message = input("You: ").strip()

        if not user_message:
            continue

        if user_message.lower() in ["exit", "quit", "bye"]:
            print("\nSmart Agri: Goodbye! 🌱")
            break

        # Step 1 — Identify what the user is asking
        intent = predict_intent(
            classifier,
            user_message
        )

        # Step 2 — Generate answer using the report
        response = generate_response(
            intent,
            report
        )

        print(f"\nSmart Agri: {response}\n")


if __name__ == "__main__":
    main()