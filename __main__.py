import pulumi
import pulumi_azure_native as azure_native

# Get the config object for this stack
config = pulumi.Config()

# Get the resource group name and location from the config
resource_group_name = config.require("resource_group_name")
location = config.require("location")

# Create the resource group
resource_group = azure_native.resources.ResourceGroup(
    resource_group_name,
    resource_group_name=resource_group_name,
    location=location
)

# Get the virtual network details from the config
vnet_name = config.require("vnet_name")
address_prefix = config.require("address_prefix")

# Create the virtual network
virtual_network = azure_native.network.VirtualNetwork(
    vnet_name,
    location=location,
    resource_group_name=resource_group.name,
    address_space=azure_native.network.AddressSpaceArgs(
        address_prefixes=[address_prefix],
    )
)

# Get the subnet details from the config
subnet_id = None
subnet_name = config.get("subnet_name")
if subnet_name:
    # Check if the subnet exists in the virtual network
    subnet = next((subnet for subnet in virtual_network.subnets if subnet.name == subnet_name), None)
    if subnet:
        subnet_id = subnet.id

# Create the MySQL server
mysql_server_name = config.require("mysql_server_name")
admin_login = config.require("admin_login")
admin_password = config.require_secret("admin_password")
db_name = config.require("db_name")

mysql_server = azure_native.dbformysql.Server(
    mysql_server_name,
    administrator_login=admin_login,
    administrator_login_password=admin_password,
    location=location,
    resource_group_name=resource_group.name,
    sku=azure_native.dbformysql.SkuArgs(
        name="Standard_B1ms",  # Example SKU, adjust as needed
        tier=azure_native.dbformysql.SkuTier.GENERAL_PURPOSE
        )
)
mysql_server_configuration = azure_native.dbformysql.Configuration(
    "mysqlServerConfiguration",
    resource_group_name=resource_group.name,
    server_name=mysql_server.name,
    configuration_name="require_secure_transport",
    value="OFF"  # Disable SSL
)
# Generate the connection string for MySQL server
connection_string = pulumi.Output.all(
    mysql_server.name,
    admin_login,
    admin_password,
    db_name
).apply(lambda args:
    f"Server=tcp:{args[0]}.mysql.database.azure.com;Database={args[3]};User ID={args[1]}@{args[0]};Password={args[2]};Encrypt=true;Connection Timeout=30;"
)

# Get the CDN profile details from the config
cdn_profile_name = config.require("cdn_profile_name")

# Create the CDN profile
cdn_profile = azure_native.cdn.Profile(
    cdn_profile_name,
    location="Global",
    profile_name=cdn_profile_name,
    resource_group_name=resource_group.name,
    sku=azure_native.cdn.SkuArgs(
        name=azure_native.cdn.SkuName.STANDARD_MICROSOFT
    )
)

# Get the CDN endpoint details from the config
cdn_endpoint_name = config.require("cdn_endpoint_name")
origin_hostname = config.require("origin_hostname")

cdn_endpoint = azure_native.cdn.Endpoint(
    cdn_endpoint_name,
    location="Global",
    profile_name=cdn_profile.name,
    resource_group_name=resource_group.name,
    is_compression_enabled=False,
    is_http_allowed=True,
    is_https_allowed=True,
    query_string_caching_behavior=azure_native.cdn.QueryStringCachingBehavior.IGNORE_QUERY_STRING,
    content_types_to_compress=[],
    tags={},
    origins=[
        azure_native.cdn.DeepCreatedOriginArgs(
            name="origin1",
            host_name=origin_hostname,
            http_port=80,
            https_port=443,
        )
    ]
)

# Get the storage account details from the config
storage_account_name = config.require("storage_account_name")

# Create the storage account
storage_account = azure_native.storage.StorageAccount(
    storage_account_name,
    resource_group_name=resource_group.name,
    location=location,
    sku=azure_native.storage.SkuArgs(
        name=azure_native.storage.SkuName.STANDARD_RAGRS,
    ),
    kind=azure_native.storage.Kind.STORAGE_V2,
    enable_https_traffic_only=True,
)

# Get the App Service Plan details from the config
app_service_plan_name = config.require("app_service_plan_name")

# Create an Azure App Service Plan
app_service_plan = azure_native.web.AppServicePlan(
    app_service_plan_name,
    resource_group_name=resource_group.name,
    location=location,
    kind='Linux',  # Specify Linux for Docker deployments
    sku=azure_native.web.SkuDescriptionArgs(
        name='B1',  # Choose the size that fits your needs
        tier='Basic',
        size='B1',
        family='B',
        capacity=1
    ),
    reserved=True  # Required for Linux plan
)

# Get the App Service details from the config
app_service_name = config.require("app_service_name")

# Web App with Linux container and site configuration
web_app = azure_native.web.WebApp(
    app_service_name,
    resource_group_name=resource_group.name,
    location="East US",
    server_farm_id=app_service_plan.id,
    site_config=azure_native.web.SiteConfigArgs(
        app_settings=[  # Environment variables can be set here
            azure_native.web.NameValuePairArgs(
                name='WEBSITES_ENABLE_APP_SERVICE_STORAGE',
                value='false'
            ),
            azure_native.web.NameValuePairArgs(
                name='DB_HOST',
                value=mysql_server.fully_qualified_domain_name
            ),
            azure_native.web.NameValuePairArgs(
                name='DB_LOGIN',
                value=admin_login
            ),
            azure_native.web.NameValuePairArgs(
                name='DB_PASSWORD',
                value=admin_password
            ),
            azure_native.web.NameValuePairArgs(
                name='DB_NAME',
                value=db_name
            ),
        ],
        always_on=True,
        linux_fx_version=f'DOCKER|wordpress:latest'  # Format for Docker Hub images
    ),
    https_only=True  # Force HTTPS for security reasons
)

# Export the resource names for reference
pulumi.export("resource_group_name", resource_group.name)
pulumi.export("virtual_network_name", virtual_network.name)
pulumi.export("mysql_server_name", mysql_server.name)
pulumi.export("cdn_profile_name", cdn_profile.name)
pulumi.export("cdn_endpoint_name", cdn_endpoint.name)
pulumi.export("storage_account_name", storage_account.name)
pulumi.export("app_service_plan_name", app_service_plan.name)
pulumi.export("app_service_name", web_app.name)
