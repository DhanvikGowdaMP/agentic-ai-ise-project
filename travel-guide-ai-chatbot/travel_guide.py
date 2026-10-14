
# Agentic AI-Based Travel Guide
# Python-only version

def travel_guide():
    print("=" * 40)
    print("  AGENTIC AI-BASED TRAVEL GUIDE")
    print("=" * 40)

    destination = input("Enter your destination: ").strip()
    days = int(input("Enter number of travel days: "))
    budget = float(input("Enter your total budget (Rs): "))

    interests = input(
        "Enter your interests (nature, temples, adventure, history): "
    ).lower()

    print("\n" + "=" * 40)
    print("         YOUR TRAVEL PLAN")
    print("=" * 40)

    print(f"Destination : {destination}")
    print(f"Duration    : {days} days")
    print(f"Budget      : Rs. {budget:.2f}")
    print(f"Interests   : {interests}")

    print("\nSuggested itinerary:")

    for day in range(1, days + 1):
        print(f"\nDay {day}: Explore {destination}")

        if "nature" in interests:
            print("- Visit scenic viewpoints and natural attractions")

        if "temple" in interests:
            print("- Visit local temples and cultural landmarks")

        if "adventure" in interests:
            print("- Explore available outdoor activities")

        if "history" in interests:
            print("- Discover historical sites and museums")

        if not any(
            interest in interests
            for interest in ["nature", "temple", "adventure", "history"]
        ):
            print("- Explore popular local attractions")

    daily_budget = budget / days

    print(f"\nSuggested daily budget: Rs. {daily_budget:.2f}")
    print("\nHave a great trip!")


if __name__ == "__main__":
    try:
        travel_guide()
    except ValueError:
        print("Please enter valid numbers for days and budget.")
