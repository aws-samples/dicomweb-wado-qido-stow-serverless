from constructs import Construct

from aws_cdk import aws_cloudfront as cloudfront, aws_cloudfront_origins as origins, Duration


class CloudFront(Construct):
    def __init__(
        self, scope: Construct, id: str, ohif_viewer_bucket, static_web_bucket, api_url, stow_url,  config, **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Create CloudFront distribution - use OHIF viewer as the default behavior
        self.distribution = cloudfront.Distribution(
            self,
            "CloudFront",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(ohif_viewer_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
            ),
            comment='Static DICOM Web',
            default_root_object='index.html',
        )

        # Add dicomweb behavior
        self.distribution.add_behavior(
            "/dicomweb*",
            origins.S3Origin(static_web_bucket),
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
        )

        # For QIDO requests, forward and cache query strings
        query_string_cache_policy = cloudfront.CachePolicy(
            self,
            "QueryStringCachePolicy",
            comment="Cache Query Strings Only",
            query_string_behavior=cloudfront.CacheQueryStringBehavior.all(),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
            header_behavior=cloudfront.CacheHeaderBehavior.none(),
            enable_accept_encoding_brotli=True,
            enable_accept_encoding_gzip=True,
            min_ttl=Duration.seconds(config["min_ttl"]),
            default_ttl=Duration.seconds(config["default_ttl"]),
            max_ttl=Duration.seconds(config["max_ttl"]),
        )
        query_string_origin_request_policy = cloudfront.OriginRequestPolicy(
            self,
            "QueryStringOriginRequestPolicy",
            comment="Origin Request Allow Query Strings Only",
            query_string_behavior=cloudfront.OriginRequestQueryStringBehavior.all(),
            cookie_behavior=cloudfront.OriginRequestCookieBehavior.none(),
            header_behavior=cloudfront.OriginRequestHeaderBehavior.none(),
        )
        self.distribution.add_behavior(
            "/qido*",
            origins.HttpOrigin(api_url, origin_path='/prod'),
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            cache_policy=query_string_cache_policy,
            origin_request_policy=query_string_origin_request_policy,
        )
        self.distribution.add_behavior(
            "/studies*",
            origins.HttpOrigin(stow_url, origin_path='/studies'),
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL
        )