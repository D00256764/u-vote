#!/usr/bin/env python3
"""
U-Vote Kubernetes Platform Setup Script
Automates the deployment of the U-Vote platform infrastructure
"""

import subprocess
import sys
import time
import argparse
from pathlib import Path
from typing import Tuple, Optional

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(message: str):
    """Print a formatted header message"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")

def print_step(step_num: int, message: str):
    """Print a step message"""
    print(f"{Colors.CYAN}{Colors.BOLD}[Step {step_num}]{Colors.ENDC} {message}")

def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")

def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.RED}❌ {message}{Colors.ENDC}")

def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")

def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.ENDC}")

def run_command(command: list, check: bool = True, capture_output: bool = False) -> Tuple[bool, str, str]:
    """
    Run a shell command and return success status and output
    
    Args:
        command: List of command arguments
        check: Whether to raise exception on non-zero exit
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        if capture_output:
            result = subprocess.run(
                command,
                check=check,
                capture_output=True,
                text=True
            )
            return True, result.stdout, result.stderr
        else:
            result = subprocess.run(command, check=check)
            return result.returncode == 0, "", ""
    except subprocess.CalledProcessError as e:
        return False, e.stdout if hasattr(e, 'stdout') else "", e.stderr if hasattr(e, 'stderr') else ""
    except FileNotFoundError:
        return False, "", f"Command not found: {command[0]}"

def check_prerequisites() -> bool:
    """Check if required tools are installed"""
    print_step(0, "Checking prerequisites...")
    
    required_tools = {
        'docker': ['docker', '--version'],
        'kubectl': ['kubectl', 'version', '--client', '--short'],
        'kind': ['kind', 'version'],
        'helm': ['helm', 'version', '--short']
    }
    
    all_present = True
    for tool, command in required_tools.items():
        success, stdout, stderr = run_command(command, check=False, capture_output=True)
        if success:
            version = stdout.strip().split('\n')[0] if stdout else "installed"
            print_success(f"{tool}: {version}")
        else:
            print_error(f"{tool} not found")
            all_present = False
    
    if not all_present:
        print_error("Missing required tools. Please install them first.")
        return False
    
    print_success("All prerequisites met")
    return True

def get_project_paths() -> Tuple[Path, Path]:
    """Get the project directory paths"""
    # Assuming script is in /u-vote/plat_scripts
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    k8s_dir = project_root / "uvote-platform" / "k8s"
    kind_config = project_root / "uvote-platform" / "kind-config.yaml"
    
    return project_root, k8s_dir, kind_config

def check_cluster_exists() -> bool:
    """Check if the uvote cluster already exists"""
    success, stdout, _ = run_command(['kind', 'get', 'clusters'], capture_output=True, check=False)
    return success and 'uvote' in stdout

def create_kind_cluster(kind_config: Path) -> bool:
    """Create Kind cluster"""
    print_step(1, "Creating Kind cluster...")
    
    if check_cluster_exists():
        print_warning("Cluster 'uvote' already exists")
        response = input("Delete and recreate? (y/n): ").lower()
        if response == 'y':
            print_info("Deleting existing cluster...")
            run_command(['kind', 'delete', 'cluster', '--name', 'uvote'])
        else:
            print_info("Using existing cluster")
            return True
    
    if not kind_config.exists():
        print_error(f"Kind config not found: {kind_config}")
        return False
    
    print_info("Creating cluster (this takes 1-2 minutes)...")
    success, stdout, stderr = run_command(
        ['kind', 'create', 'cluster', '--config', str(kind_config), '--name', 'uvote'],
        check=False
    )
    
    if not success:
        print_error("Failed to create cluster")
        print(stderr)
        return False
    
    print_success("Cluster created successfully")
    
    # Verify nodes
    success, stdout, _ = run_command(['kubectl', 'get', 'nodes'], capture_output=True, check=False)
    if success:
        print_info("Cluster nodes:")
        print(stdout)
    
    return True

def install_calico() -> bool:
    """Install Calico CNI"""
    print_step(2, "Installing Calico CNI...")
    
    # Install Calico operator
    print_info("Installing Calico operator...")
    success, _, stderr = run_command([
        'kubectl', 'create', '-f',
        'https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml'
    ], check=False)
    
    if not success and 'already exists' not in stderr:
        print_error("Failed to install Calico operator")
        return False
    
    # Install Calico custom resources
    print_info("Installing Calico custom resources...")
    success, _, stderr = run_command([
        'kubectl', 'create', '-f',
        'https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/custom-resources.yaml'
    ], check=False)
    
    if not success and 'already exists' not in stderr:
        print_error("Failed to install Calico custom resources")
        return False
    
    # Wait for Calico to be ready
    print_info("Waiting for Calico to be ready (this may take 2-3 minutes)...")
    time.sleep(30)  # Initial wait
    
    success, _, _ = run_command([
        'kubectl', 'wait', '--for=condition=Ready',
        'pods', '--all', '-n', 'calico-system',
        '--timeout=300s'
    ], check=False)
    
    if not success:
        print_warning("Calico pods may still be starting")
        return True  # Continue anyway
    
    print_success("Calico installed and ready")
    
    # Verify nodes are Ready
    success, stdout, _ = run_command(['kubectl', 'get', 'nodes'], capture_output=True, check=False)
    if success:
        print_info("Node status:")
        print(stdout)
    
    return True

def apply_namespaces(k8s_dir: Path) -> bool:
    """Apply namespace configuration"""
    print_step(3, "Creating namespaces...")
    
    namespaces_file = k8s_dir / "namespaces" / "namespaces.yaml"
    if not namespaces_file.exists():
        print_error(f"Namespaces file not found: {namespaces_file}")
        return False
    
    success, _, stderr = run_command([
        'kubectl', 'apply', '-f', str(namespaces_file)
    ], check=False)
    
    if not success:
        print_error("Failed to create namespaces")
        print(stderr)
        return False
    
    print_success("Namespaces created")
    
    # Verify namespaces
    success, stdout, _ = run_command([
        'kubectl', 'get', 'namespaces'
    ], capture_output=True, check=False)
    
    if success:
        print_info("Namespaces:")
        for line in stdout.split('\n'):
            if 'uvote' in line:
                print(f"  {line}")
    
    return True

def deploy_database(k8s_dir: Path) -> bool:
    """Deploy PostgreSQL database"""
    print_step(4, "Deploying PostgreSQL database...")
    
    db_dir = k8s_dir / "database"
    
    # Apply secret
    print_info("Creating database secret...")
    secret_file = db_dir / "db-secret.yaml"
    if not secret_file.exists():
        print_error(f"Secret file not found: {secret_file}")
        return False
    
    success, _, _ = run_command([
        'kubectl', 'apply', '-f', str(secret_file)
    ], check=False)
    
    if not success:
        print_error("Failed to create database secret")
        return False
    
    # Apply PVC
    print_info("Creating persistent volume claim...")
    pvc_file = db_dir / "db-pvc.yaml"
    if not pvc_file.exists():
        print_error(f"PVC file not found: {pvc_file}")
        return False
    
    success, _, _ = run_command([
        'kubectl', 'apply', '-f', str(pvc_file)
    ], check=False)
    
    if not success:
        print_error("Failed to create PVC")
        return False
    
    # Apply deployment
    print_info("Creating database deployment...")
    deployment_file = db_dir / "db-deployment.yaml"
    if not deployment_file.exists():
        print_error(f"Deployment file not found: {deployment_file}")
        return False
    
    success, _, _ = run_command([
        'kubectl', 'apply', '-f', str(deployment_file)
    ], check=False)
    
    if not success:
        print_error("Failed to create database deployment")
        return False
    
    # Wait for database to be ready
    print_info("Waiting for PostgreSQL to be ready (this may take up to 2 minutes)...")
    success, _, _ = run_command([
        'kubectl', 'wait', '--for=condition=Ready',
        'pod', '-l', 'app=postgresql',
        '-n', 'uvote-dev',
        '--timeout=120s'
    ], check=False)
    
    if not success:
        print_error("PostgreSQL pod did not become ready in time")
        return False
    
    print_success("PostgreSQL deployed and ready")
    
    # Show status
    success, stdout, _ = run_command([
        'kubectl', 'get', 'pods,svc', '-n', 'uvote-dev'
    ], capture_output=True, check=False)
    
    if success:
        print_info("Database status:")
        print(stdout)
    
    return True

def apply_database_schema(k8s_dir: Path) -> bool:
    """Apply database schema"""
    print_step(5, "Applying database schema...")
    
    schema_file = k8s_dir / "database" / "schema.sql"
    if not schema_file.exists():
        print_error(f"Schema file not found: {schema_file}")
        return False
    
    # Get PostgreSQL pod name
    success, stdout, _ = run_command([
        'kubectl', 'get', 'pod',
        '-n', 'uvote-dev',
        '-l', 'app=postgresql',
        '-o', 'jsonpath={.items[0].metadata.name}'
    ], capture_output=True, check=False)
    
    if not success or not stdout:
        print_error("Failed to get PostgreSQL pod name")
        return False
    
    pod_name = stdout.strip()
    print_info(f"Applying schema to pod: {pod_name}")
    
    # Read schema file
    with open(schema_file, 'r') as f:
        schema_content = f.read()
    
    # Apply schema
    process = subprocess.Popen(
        ['kubectl', 'exec', '-i', '-n', 'uvote-dev', pod_name, '--',
         'psql', '-U', 'uvote_admin', '-d', 'uvote'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    stdout, stderr = process.communicate(input=schema_content)
    
    if process.returncode != 0:
        print_error("Failed to apply schema")
        print(stderr)
        return False
    
    print_success("Database schema applied")
    
    # Verify tables
    print_info("Verifying tables...")
    success, stdout, _ = run_command([
        'kubectl', 'exec', '-i', '-n', 'uvote-dev', pod_name, '--',
        'psql', '-U', 'uvote_admin', '-d', 'uvote', '-c', '\\dt'
    ], capture_output=True, check=False)
    
    if success:
        print(stdout)
    
    return True

def apply_network_policies(k8s_dir: Path) -> bool:
    """Apply network policies"""
    print_step(6, "Applying network policies...")
    
    network_policies_dir = k8s_dir / "network-policies"
    
    if not network_policies_dir.exists() or not any(network_policies_dir.iterdir()):
        print_warning("No network policies found, skipping...")
        return True
    
    # Apply all network policy files
    policy_files = sorted(network_policies_dir.glob("*.yaml"))
    if not policy_files:
        print_warning("No network policy YAML files found")
        return True
    
    for policy_file in policy_files:
        print_info(f"Applying {policy_file.name}...")
        success, _, stderr = run_command([
            'kubectl', 'apply', '-f', str(policy_file)
        ], check=False)
        
        if not success:
            print_error(f"Failed to apply {policy_file.name}")
            print(stderr)
            return False
    
    print_success("Network policies applied")
    
    # Show applied policies
    success, stdout, _ = run_command([
        'kubectl', 'get', 'networkpolicies', '-n', 'uvote-dev'
    ], capture_output=True, check=False)
    
    if success:
        print_info("Network policies:")
        print(stdout)
    
    return True

def install_ingress_controller() -> bool:
    """Install Nginx Ingress Controller"""
    print_step(7, "Installing Nginx Ingress Controller...")
    
    # Add Helm repo
    print_info("Adding ingress-nginx Helm repository...")
    run_command(['helm', 'repo', 'add', 'ingress-nginx', 
                 'https://kubernetes.github.io/ingress-nginx'], check=False)
    run_command(['helm', 'repo', 'update'], check=False)
    
    # Install ingress controller
    print_info("Installing ingress-nginx...")
    success, _, stderr = run_command([
        'helm', 'install', 'ingress-nginx', 'ingress-nginx/ingress-nginx',
        '--namespace', 'ingress-nginx',
        '--create-namespace'
    ], check=False)
    
    if not success and 'already exists' not in stderr:
        print_error("Failed to install ingress controller")
        return False
    
    # Wait for ingress controller
    print_info("Waiting for ingress controller to be ready...")
    success, _, _ = run_command([
        'kubectl', 'wait', '--namespace', 'ingress-nginx',
        '--for=condition=ready', 'pod',
        '--selector=app.kubernetes.io/component=controller',
        '--timeout=120s'
    ], check=False)
    
    if not success:
        print_warning("Ingress controller may still be starting")
        return True  # Continue anyway
    
    print_success("Ingress controller installed")
    return True

def verify_setup() -> bool:
    """Verify the complete setup"""
    print_step(8, "Verifying setup...")
    
    checks_passed = True
    
    # Check nodes
    print_info("Checking cluster nodes...")
    success, stdout, _ = run_command(['kubectl', 'get', 'nodes'], capture_output=True, check=False)
    if success and 'Ready' in stdout:
        ready_count = stdout.count('Ready')
        print_success(f"{ready_count} nodes ready")
        print(stdout)
    else:
        print_error("Nodes not ready")
        checks_passed = False
    
    # Check Calico
    print_info("Checking Calico pods...")
    success, stdout, _ = run_command([
        'kubectl', 'get', 'pods', '-n', 'calico-system'
    ], capture_output=True, check=False)
    if success and 'Running' in stdout:
        running_count = stdout.count('Running')
        print_success(f"{running_count} Calico pods running")
    else:
        print_error("Calico pods not running")
        checks_passed = False
    
    # Check database
    print_info("Checking database...")
    success, stdout, _ = run_command([
        'kubectl', 'get', 'pods', '-n', 'uvote-dev', '-l', 'app=postgresql'
    ], capture_output=True, check=False)
    if success and 'Running' in stdout:
        print_success("Database running")
        print(stdout)
    else:
        print_error("Database not running")
        checks_passed = False
    
    # Check namespaces
    print_info("Checking namespaces...")
    success, stdout, _ = run_command([
        'kubectl', 'get', 'namespaces'
    ], capture_output=True, check=False)
    if success:
        uvote_ns = [line for line in stdout.split('\n') if 'uvote' in line]
        if len(uvote_ns) >= 3:
            print_success(f"{len(uvote_ns)} U-Vote namespaces found")
            for ns in uvote_ns:
                print(f"  {ns}")
        else:
            print_error("Missing U-Vote namespaces")
            checks_passed = False
    
    return checks_passed

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='U-Vote Kubernetes Platform Setup',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full setup
  python setup_k8s_platform.py
  
  # Skip cluster creation (use existing)
  python setup_k8s_platform.py --skip-cluster
  
  # Skip ingress controller
  python setup_k8s_platform.py --skip-ingress
        """
    )
    
    parser.add_argument('--skip-prereq', action='store_true',
                       help='Skip prerequisite checks')
    parser.add_argument('--skip-cluster', action='store_true',
                       help='Skip cluster creation (use existing)')
    parser.add_argument('--skip-calico', action='store_true',
                       help='Skip Calico installation')
    parser.add_argument('--skip-ingress', action='store_true',
                       help='Skip ingress controller installation')
    parser.add_argument('--skip-verify', action='store_true',
                       help='Skip final verification')
    
    args = parser.parse_args()
    
    print_header("U-Vote Kubernetes Platform Setup")
    print_info("Starting automated platform deployment...")
    
    # Get paths
    try:
        project_root, k8s_dir, kind_config = get_project_paths()
        print_info(f"Project root: {project_root}")
        print_info(f"K8s manifests: {k8s_dir}")
        print_info(f"Kind config: {kind_config}")
    except Exception as e:
        print_error(f"Failed to determine project paths: {e}")
        sys.exit(1)
    
    # Check prerequisites
    if not args.skip_prereq:
        if not check_prerequisites():
            sys.exit(1)
    
    # Create cluster
    if not args.skip_cluster:
        if not create_kind_cluster(kind_config):
            print_error("Cluster creation failed")
            sys.exit(1)
    else:
        print_info("Skipping cluster creation (using existing)")
    
    # Install Calico
    if not args.skip_calico:
        if not install_calico():
            print_error("Calico installation failed")
            sys.exit(1)
    else:
        print_info("Skipping Calico installation")
    
    # Apply namespaces
    if not apply_namespaces(k8s_dir):
        print_error("Namespace creation failed")
        sys.exit(1)
    
    # Deploy database
    if not deploy_database(k8s_dir):
        print_error("Database deployment failed")
        sys.exit(1)
    
    # Apply schema
    if not apply_database_schema(k8s_dir):
        print_error("Schema application failed")
        sys.exit(1)
    
    # Apply network policies
    if not apply_network_policies(k8s_dir):
        print_warning("Network policy application had issues (non-critical)")
    
    # Install ingress
    if not args.skip_ingress:
        if not install_ingress_controller():
            print_warning("Ingress controller installation had issues (non-critical)")
    else:
        print_info("Skipping ingress controller installation")
    
    # Verify setup
    if not args.skip_verify:
        if verify_setup():
            print_header("✅ Platform Setup Complete!")
            print_success("All components deployed and verified")
            print_info("\nNext steps:")
            print("  1. Test database: kubectl exec -it -n uvote-dev <pod-name> -- psql -U uvote_admin -d uvote")
            print("  2. Deploy application services")
            print("  3. Configure ingress routing")
        else:
            print_header("⚠️  Setup Complete with Warnings")
            print_warning("Some components may need attention")
    else:
        print_header("✅ Setup Complete!")
        print_info("Verification skipped")
    
    print_info("\nUseful commands:")
    print("  kubectl get nodes                    # Check cluster nodes")
    print("  kubectl get pods -n uvote-dev        # Check database")
    print("  kubectl get pods -n calico-system    # Check Calico")
    print("  kind delete cluster --name uvote     # Delete cluster")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nSetup interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)