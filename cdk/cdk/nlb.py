"""
Generate the network load balancer.
SPDX-License-Identifier: Apache 2.0
"""

from constructs import Construct
import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2,  aws_elasticloadbalancingv2 as elbv2 , aws_s3 as s3


class StowNLB(Construct):
    _tg = None
    _lb = None
    def __init__(self, scope: Construct, id: str,  vpc: ec2.Vpc, certificate_config: dict, dicom_s3 : s3.IBucket , **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self._lb = elbv2.NetworkLoadBalancer(self, "NLB" , vpc=vpc , internet_facing=True)
        self._lb.log_access_logs(bucket=dicom_s3 , prefix="AccessLogs")
        
        if (certificate_config["certificate_mode"].upper() == "ACM"):
            certificate_arn = certificate_config["certificate_arn"]
            listener = self._lb.add_listener(id="TCPListener" , port=443 ,ssl_policy=elbv2.SslPolicy.RECOMMENDED , protocol=elbv2.Protocol.TLS , certificates= [elbv2.ListenerCertificate(certificate_arn)])
            self._tg = elbv2.NetworkTargetGroup(self,"tg-stowrstos3",target_type=elbv2.TargetType.IP,port=443,vpc=vpc, protocol= elbv2.Protocol.TLS , preserve_client_ip=True)
        else:
            listener = self._lb.add_listener(id="TCPListener" , port=443)
            self._tg = elbv2.NetworkTargetGroup(self,"tg-stowrstos3",target_type=elbv2.TargetType.IP,port=443,vpc=vpc, protocol= elbv2.Protocol.TCP, preserve_client_ip=True)
        
        
        listener.add_target_groups("tg",self._tg)

    def getTargetGroup(self):
        print(str(self._tg))
        return self._tg

    def getLoadBalancer(self):
        return self._lb