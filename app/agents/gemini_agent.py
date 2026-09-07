 intent = self._detect_intent(query)
        if not is_valid:
            intent = "unsupported"

        logger.info(f"User query: {original_query}")
        logger.info(f"Detected intent: {intent}")
        logger.info(f"Confidence: {confidence:.2f}")

        if intent == "unsupported":
            logger.info("MCP tool: none")
            logger.info("Chart: none")
            return self._error_response(
                f"I couldn't identify a supported analytics request from '{original_query}'. Please ask a question about revenue, orders, categories, payments, reviews, sellers, or delivery performance.",
                "unsupported_intent"
            )
