def generate_response(intent, report):
    """
    Generate a response using the predicted intent
    and the Smart Agri report.
    """

    if intent == "GREETING":
        return (
            "Hello! I'm the Smart Agri assistant. "
            "I can help you understand your crop recommendation, "
            "soil analysis, fertilizer recommendation, and yield prediction."
        )

    if intent == "HELP":
        return (
            "I can help you with:\n"
            "• Crop recommendations\n"
            "• Crop recommendation probabilities\n"
            "• Soil nutrient status\n"
            "• Fertilizer recommendations\n"
            "• Fertilizer dosage and application\n"
            "• Yield prediction and interpretation"
        )

    if intent == "SYSTEM_OVERVIEW":
        return (
            "Smart Agri is a decision-support system that analyzes "
            "your soil and environmental inputs to recommend suitable "
            "crops, identify soil nutrient gaps, suggest fertilizers, "
            "and predict yield."
        )

    if intent == "SUPPORTED_CROPS":
        crops = [
            "Jowar",
            "Groundnut",
            "Cotton",
            "Sugarcane",
            "Wheat"
        ]

        return (
            "Smart Agri currently supports soil adjustment and "
            "fertilizer recommendations for: "
            + ", ".join(crops)
            + "."
        )

    # --------------------------------------------------
    # CROP RECOMMENDATION
    # --------------------------------------------------

    if intent == "CROP_RECOMMENDATION":

        crop = report["chosen_crop"]

        return (
            f"Based on your current soil and environmental inputs, "
            f"Smart Agri recommends {crop} as the top crop."
        )

    if intent == "CROP_RECOMMENDATION_EXPLANATION":

        crop = report["chosen_crop"]

        top_crop = report["top_5_crops"][0]

        probability = top_crop["probability"] * 100

        return (
            f"{crop} was recommended because it received the highest "
            f"prediction probability of {probability:.1f}% among the "
            f"crops considered by the crop model."
        )

    if intent == "CROP_PROBABILITY":

        recommendations = report["top_5_crops"]

        lines = ["Here are the top crop predictions:"]

        for item in recommendations:
            probability = item["probability"] * 100

            lines.append(
                f"• {item['crop']}: {probability:.1f}%"
            )

        return "\n".join(lines)

    # --------------------------------------------------
    # SOIL ANALYSIS
    # --------------------------------------------------

    if intent == "SOIL_ANALYSIS":

        soil = report["soil_input"]

        return (
            f"Your current soil readings are:\n"
            f"• Nitrogen: {soil['Nitrogen']} kg/ha\n"
            f"• Phosphorus: {soil['Phosphorus']} kg/ha\n"
            f"• Potassium: {soil['Potassium']} kg/ha\n"
            f"• pH: {soil['pH']}\n"
            f"• Temperature: {soil['Temperature']} °C\n"
            f"• Rainfall: {soil['Rainfall']} mm"
        )

        # --------------------------------------------------
    # INDIVIDUAL SOIL NUTRIENTS
    # --------------------------------------------------

    nutrient_intents = {
        "SOIL_NITROGEN": "Nitrogen",
        "SOIL_PHOSPHORUS": "Phosphorus",
        "SOIL_POTASSIUM": "Potassium",
        "SOIL_PH": "pH"
    }

    if intent in nutrient_intents:

        nutrient = nutrient_intents[intent]

        soil_adjustment = report.get("soil_adjustment", {})

        # Crop is not supported by the soil adjustment engine
        if nutrient not in soil_adjustment:

            current_value = report["soil_input"].get(nutrient)

            if nutrient == "pH":
                unit = ""
            else:
                unit = " kg/ha"

            return (
                f"Your {nutrient} level is "
                f"{current_value}{unit}. "
                f"However, Smart Agri does not currently have "
                f"soil adjustment data for {report['chosen_crop']}, "
                f"so I cannot determine whether this value is "
                f"Low, High, or Optimal for that crop."
            )

        # Crop is supported by the soil adjustment engine
        info = soil_adjustment[nutrient]

        if nutrient == "pH":
            unit = ""
        else:
            unit = " kg/ha"

        return (
            f"Your {nutrient} level is {info['current']}{unit}. "
            f"For {report['chosen_crop']}, the ideal value used by "
            f"Smart Agri is {info['ideal']}{unit}. "
            f"Your status is {info['status']}."
        )
        
    

    # --------------------------------------------------
    # SOIL STATUS
    # --------------------------------------------------

    if intent == "SOIL_STATUS_EXPLANATION":

        return (
            "Smart Agri uses three soil status categories:\n"
            "• Low — the current value is below the ideal range.\n"
            "• High — the current value is above the ideal range.\n"
            "• Optimal — the value is within the defined tolerance range."
        )

    # --------------------------------------------------
    # FERTILIZER
    # --------------------------------------------------

    if intent == "FERTILIZER_RECOMMENDATION":

        fertilizer = report.get("fertilizer")

        if not fertilizer or not fertilizer.get("gap_analysis"):
            return (
                f"Smart Agri does not currently have fertilizer "
                f"recommendations for {report['chosen_crop']}. "
                f"The fertilizer recommendation module currently "
                f"supports Jowar, Groundnut, Cotton, Sugarcane, and Wheat."
            )

        if not fertilizer["action_needed"]:
            return (
                f"Your soil is well-balanced for "
                f"{report['chosen_crop']}. "
                f"No nutrient correction is currently needed."
            )

        lines = ["Based on your soil analysis:"]

        for rec in fertilizer["generic_recs"]:

            if rec["condition"] == "Low":
                lines.append(
                    f"• {rec['nutrient']} is Low → "
                    f"{rec['fertilizer']}"
                )

            elif rec["condition"] == "High":
                lines.append(
                    f"• {rec['nutrient']} is High → "
                    f"{rec['fertilizer']}"
                )

        if fertilizer["crop_primary"]:
            lines.append(
                f"\nPrimary fertilizer for "
                f"{report['chosen_crop']}: "
                f"{fertilizer['crop_primary']['fertilizer']}"
            )

        return "\n".join(lines)

    if intent == "FERTILIZER_DOSAGE":

        recommendations = report["fertilizer"]["generic_recs"]

        if not recommendations:
            return (
                "No specific fertilizer dosage is currently "
                "required because your soil is within the optimal range."
            )

        lines = ["Recommended fertilizer application:"]

        for rec in recommendations:

            lines.append(
                f"• {rec['fertilizer']}: {rec['dose_note']}"
            )

        return "\n".join(lines)

    if intent == "WHY_FERTILIZER_NEEDED":

        recommendations = report["fertilizer"]["generic_recs"]

        if not recommendations:
            return (
                "No corrective fertilizer is currently required "
                "because your soil values are within the optimal range."
            )

        lines = []

        for rec in recommendations:

            lines.append(
                f"• {rec['fertilizer']}: {rec['reason']}"
            )

        return "\n".join(lines)

    if intent == "FERTILIZER_EXPLANATION":

        recommendations = report["fertilizer"]["generic_recs"]

        if not recommendations:
            return (
                "There are currently no corrective fertilizer "
                "recommendations in your report."
            )

        lines = ["Your fertilizer recommendations are:"]

        for rec in recommendations:

            lines.append(
                f"• {rec['fertilizer']} "
                f"({rec['npk_ratio']}) — "
                f"{rec['reason']}"
            )

        return "\n".join(lines)

    # --------------------------------------------------
    # YIELD
    # --------------------------------------------------

    if intent == "YIELD_PREDICTION":

        yield_info = report["yield_prediction"]

        return (
            f"Your predicted yield for {report['chosen_crop']} "
            f"is {yield_info['predicted_yield_kg_ha']:,.1f} kg/ha."
        )

    if intent == "YIELD_EXPLANATION":

        yield_info = report["yield_prediction"]

        return yield_info["interpretation"]

    if intent == "YIELD_FACTORS":

        return (
            "The Smart Agri yield prediction uses the available "
            "soil and environmental inputs from your analysis, "
            "including Nitrogen, Phosphorus, Potassium, temperature, "
            "rainfall, pH, and the selected crop."
        )

    if intent == "YIELD_STATUS_EXPLANATION":

        return (
            "Smart Agri interprets predicted yield using categories "
            "such as Moderate, Good, and High. These indicate the "
            "model's interpretation of the predicted yield for the "
            "selected crop."
        )

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------

    if intent == "OUT_OF_SCOPE":

        return (
            "I'm designed specifically for Smart Agri. "
            "I can answer questions about the software, "
            "your soil analysis, crop recommendations, "
            "fertilizer recommendations, and yield prediction."
        )

    if intent == "UNKNOWN":

        return (
            "I'm not sure what you're asking. "
            "Try asking about your crop recommendation, soil, "
            "fertilizer, or yield prediction."
        )

    return (
        "I don't have an answer for that yet. "
        "Please ask something related to Smart Agri."
    )