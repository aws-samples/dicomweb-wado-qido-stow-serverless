from constructs import Construct

from aws_cdk import (
    Duration,
    aws_lambda,
    aws_lambda_python_alpha as aws_lambda_python,
    aws_logs as logs,
)


class PythonLambda(Construct):
    def __init__(self, scope: Construct, id: str, config, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        layers = []
        for l in config["layers"]:
            if l.lower() == "pydicom":
                layers.append(
                    aws_lambda_python.PythonLayerVersion(
                        self, "PyDicom", entry="../lambda_layer/pydicom"
                    )
                )
        
        if config["reserved_concurrency"]:
            self.fn = aws_lambda_python.PythonFunction(
                self,
                "Function",
                runtime=aws_lambda.Runtime.PYTHON_3_7,
                entry=config["entry"],
                index=config["index"],
                handler=config["handler"],
                timeout=Duration.minutes(config["timeout"]),
                memory_size=config["memory"],
                log_retention=logs.RetentionDays.THREE_DAYS,
                layers=layers,
                reserved_concurrent_executions = config["reserved_concurrency"],
            )
        else:
            self.fn = aws_lambda_python.PythonFunction(
                self,
                "Function",
                runtime=aws_lambda.Runtime.PYTHON_3_7,
                entry=config["entry"],
                index=config["index"],
                handler=config["handler"],
                timeout=Duration.minutes(config["timeout"]),
                memory_size=config["memory"],
                log_retention=logs.RetentionDays.THREE_DAYS,
                layers=layers,
            )
            
