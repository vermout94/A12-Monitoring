import pulumi
from pulumi_azure_native import resources, compute, storage, network
import random
import string

# Configuration
config = pulumi.Config("azure")
location = config.get("location") or "westeurope"
resource_group_name = "myresourcegroup"
vm_name = config.get("vmName") or "monitored-linux-vm"
vm_size = config.get("size") or "Standard_B1s"
admin_username = config.get("adminUsername") or "azureuser"
admin_password = config.require_secret("adminPassword")  # Retrieve encrypted password

# Generate a unique storage account name
def generate_storage_name():
    return f"metricsstorage{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"

storage_account_name = config.get("storageAccountName") or generate_storage_name()

# Step 1: Create Resource Group
resource_group = resources.ResourceGroup(
    resource_group_name,
    location=location
)

# Step 2: Create Storage Account for Boot Diagnostics
storage_account = storage.StorageAccount(
    "bootdiagnosticsstorage",
    resource_group_name=resource_group.name,
    account_name=storage_account_name,
    sku=storage.SkuArgs(
        name="Standard_LRS"
    ),
    kind="StorageV2",
    location=resource_group.location
)

# Step 3: Create Virtual Network
vnet = network.VirtualNetwork(
    "vmVNet",
    resource_group_name=resource_group.name,
    location=resource_group.location,
    address_space=network.AddressSpaceArgs(
        address_prefixes=["10.0.0.0/16"]
    )
)

# Step 4: Create Subnet
subnet = network.Subnet(
    "vmSubnet",
    resource_group_name=resource_group.name,
    virtual_network_name=vnet.name,
    address_prefix="10.0.1.0/24"
)

# Step 5: Create Public IP
public_ip = network.PublicIPAddress(
    "vmPublicIP",
    resource_group_name=resource_group.name,
    location=resource_group.location,
    public_ip_allocation_method="Dynamic"
)

# Step 6: Create Network Interface
network_interface = network.NetworkInterface(
    "vmNIC",
    resource_group_name=resource_group.name,
    location=resource_group.location,
    ip_configurations=[network.NetworkInterfaceIPConfigurationArgs(
        name="ipconfig1",
        subnet=network.SubnetArgs(
            id=subnet.id
        ),
        private_ip_allocation_method="Dynamic",
        public_ip_address=network.PublicIPAddressArgs(
            id=public_ip.id
        )
    )]
)

# Step 7: Create Virtual Machine
vm = compute.VirtualMachine(
    vm_name,
    resource_group_name=resource_group.name,
    location=resource_group.location,
    hardware_profile=compute.HardwareProfileArgs(
        vm_size=vm_size
    ),
    storage_profile=compute.StorageProfileArgs(
        os_disk=compute.OSDiskArgs(
            caching="ReadWrite",
            create_option="FromImage",
            managed_disk=compute.ManagedDiskParametersArgs(
                storage_account_type="Standard_LRS"
            )
        ),
        image_reference=compute.ImageReferenceArgs(
            publisher="Canonical",
            offer="0001-com-ubuntu-server-jammy",
            sku="22_04-lts-gen2",
            version="latest"
        )
    ),
    os_profile=compute.OSProfileArgs(
        computer_name=vm_name,
        admin_username=admin_username,
        admin_password=admin_password,  # Secure password automatically decrypted by Pulumi
        linux_configuration=compute.LinuxConfigurationArgs(
            disable_password_authentication=False  # Enable password authentication
        )
    ),
    network_profile=compute.NetworkProfileArgs(
        network_interfaces=[compute.NetworkInterfaceReferenceArgs(
            id=network_interface.id,
            primary=True
        )]
    ),
    diagnostics_profile=compute.DiagnosticsProfileArgs(
        boot_diagnostics=compute.BootDiagnosticsArgs(
            enabled=True,
            storage_uri=storage_account.primary_endpoints.apply(
                lambda endpoints: endpoints.blob
            )
        )
    )
)

# Outputs
pulumi.export("resourceGroupName", resource_group.name)
pulumi.export("storageAccountName", storage_account.name)
pulumi.export("vmName", vm.name)
pulumi.export("location", resource_group.location)
