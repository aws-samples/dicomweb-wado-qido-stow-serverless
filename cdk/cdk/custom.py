from constructs import Construct

from aws_cdk import CustomResource, custom_resources as cr, aws_logs as logs


class CustomLambdaResource(Construct):
    def __init__(self, scope: Construct, id: str, lambda_handler, cr_properties={}, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        cr_provider = cr.Provider(
            self, "CustomProvider", on_event_handler=lambda_handler, log_retention=logs.RetentionDays.THREE_DAYS
        )

        self.cr = CustomResource(
            self, "CustomResource", service_token=cr_provider.service_token, properties=cr_properties
        )
