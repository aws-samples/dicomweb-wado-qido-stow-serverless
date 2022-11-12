from constructs import Construct

from aws_cdk import aws_apigateway as apigateway, aws_logs as logs


class ApiGwLambda(Construct):
    def __init__(self, scope: Construct, id: str, handler, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        accessLogs = logs.LogGroup(self, "ApiGwAccessLog", retention=logs.RetentionDays.ONE_MONTH)

        self.apigw = apigateway.LambdaRestApi(
            self,
            "ApiGwLambda",
            handler=handler,
            deploy_options=apigateway.StageOptions(
                access_log_destination=apigateway.LogGroupLogDestination(accessLogs),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=False,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS, allow_methods=["GET"]
            ),
        )
