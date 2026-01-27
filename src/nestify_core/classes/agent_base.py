class Agent:
    """
    Base Agent class. Subclass this to create custom agent profiles.
    Override methods to customize agent behavior.
    """
    def get_name(self):
        """Return the agent's name."""
        return "base"

    def get_prompt_template(self):
        """Return the prompt template string for this agent."""
        return "You are a helpful AI assistant."

    def preprocess_input(self, user_input):
        """Optionally preprocess user input before prompt construction."""
        return user_input

    # Add more overridable methods as needed
