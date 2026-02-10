from google.cloud import secretmanager


class SecretsContainer:
    def __init__(self):
        self.project_id = "gen-lang-client-0320316404"
        self.client = secretmanager.SecretManagerServiceClient()
        self._cache = {}

    def __getattr__(self, name: str):
        if name in self._cache:
            return self._cache[name]

        try:
            resource_name = f"projects/{self.project_id}/secrets/{name}/versions/latest"
            response = self.client.access_secret_version(request={"name": resource_name})
            payload = response.payload.data.decode("UTF-8")
            self._cache[name] = payload
            return payload
        except Exception as e:
            raise AttributeError(f"Secret '{name}' not found or inaccessible in project {self.project_id}.") from e

    def list_secrets(self):
        """
        List all secrets in the given project.
        """
        parent = f"projects/{self.project_id}"
        for secret in self.client.list_secrets(request={"parent": parent}):
            print(f"Found secret: {secret.name}, {secret.create_time} ")



