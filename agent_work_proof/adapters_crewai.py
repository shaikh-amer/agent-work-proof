# agent_work_proof/adapters_crewai.py

class CrewAIAdapter:
    def __init__(self, task_type_mapping, crewai_client):
        self.task_type_mapping = task_type_mapping
        self.crewai_client = crewai_client

    def on_task_complete(self, task_id, result):
        """Handle task completion events."""
        try:
            # Map the task type to WorkCredentials
            task_type = self.task_type_mapping.get(task_id)
            if not task_type:
                raise ValueError(f"No mapping found for task_id: {task_id}")

            # Issue WorkCredentials for successful tasks
            self.issue_work_credentials(task_id, task_type, result)
        except Exception as e:
            self.handle_error(task_id, e)
            
    def issue_work_credentials(self, task_id, task_type, result):
        """Issue WorkCredentials based on task completion."""
        # Logic to issue WorkCredentials using CrewAI's API
        print(f"Issuing WorkCredentials for task_id: {task_id} of type: {task_type}")
        # Assuming a method in crewai_client handles this
        self.crewai_client.issue_credentials(task_id, result)

    def handle_error(self, task_id, error):
        """Handle errors gracefully."""
        print(f"Error processing task_id {task_id}: {str(error)}")
        # Log the error or take necessary actions
        # Additional error handling logic can be implemented here
