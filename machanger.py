"""
MAC Changer CLI Tool
--------------------
A Python tool to change, restore, or show the MAC address of a network interface on Linux.
"""

# ========== Imports and Constants ==========
import argparse
import subprocess
import re
from pathlib import Path
from datetime import datetime
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import random
import json
import os

LOG_FILE = Path.home() / ".machanger" / "machanger.log"
console = Console()

LEVEL_STYLES = {
    'info': 'cyan',
    'success': 'bold green',
    'warning': 'yellow',
    'error': 'red',
    'verbose': 'blue',
}

# ========== Output and Logging ==========
def print_colored(message, level='info'):
    """Print a message to the console with the appropriate color based on level."""
    style = LEVEL_STYLES.get(level, 'white')
    console.print(message, style=style)

def log_action(message):
    """Log actions to a file in ~/.machanger/machanger.log."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] {message}\n")
    except OSError as e:
        print(f"[machanger] Logging failed: {e}", file=sys.stderr)

# ========== Argument Parsing ==========
def get_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="machanger",
        description=(
            "A comprehensive CLI tool to change, restore, randomize, simulate, profile, "
            "and audit the MAC address of one or more network interfaces. "
            "Features include: setting a specific MAC, generating random or vendor-specific MACs, "
            "restoring original MACs (single or all), showing and logging MAC history, dry-run simulation, "
            "and exporting/importing MAC address profiles."
        ),
        epilog="""Examples:
  python3 machanger.py -i eth0 -m 00:11:22:33:44:55
  python3 machanger.py -i eth0 --restore
  python3 machanger.py --list
  python3 machanger.py -i eth0 --show
  python3 machanger.py -i eth0 --random
  python3 machanger.py -i eth0 --vendor 00:11:22
  python3 machanger.py --restore-all
  python3 machanger.py -i eth0 --history
  python3 machanger.py -i eth0 --dry-run --mac 00:11:22:33:44:55
  python3 machanger.py --export-profile myprofile
  python3 machanger.py --import-profile myprofile
        """,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-i", "--interface", metavar="INTERFACE", help="Network interface to operate on (e.g., eth0, wlan0)")
    parser.add_argument("-m", "--mac", dest="new_mac", metavar="NEW_MAC", help="New MAC address to assign to the interface (e.g., 00:11:22:33:44:55)")
    parser.add_argument("--restore", action="store_true", help="Restore the original MAC address for the interface")
    parser.add_argument("--list", dest="list_interfaces", action="store_true", help="List all available interfaces and their MAC addresses")
    parser.add_argument("--show", dest="show_mac", action="store_true", help="Show the current MAC address for the specified interface (requires -i)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--force-overwrite", dest="force_overwrite", action="store_true", help="Force overwrite the saved original MAC address")
    parser.add_argument("--random", action="store_true", help="Generate a random MAC address")
    parser.add_argument("--vendor", metavar="OUI", help="Generate a vendor-specific MAC address")
    parser.add_argument("--restore-all", action="store_true", help="Restore MAC addresses for all interfaces")
    parser.add_argument("--history", action="store_true", help="Show MAC address history")
    parser.add_argument("--dry-run", action="store_true", help="Dry run/simulation mode")
    parser.add_argument("--export-profile", metavar="PROFILE_NAME", help="Export a MAC profile")
    parser.add_argument("--import-profile", metavar="PROFILE_NAME", help="Import a MAC profile")
    return parser.parse_args()

# ========== Interface Utilities ==========
def is_valid_mac(mac):
    """Return True if the MAC address is valid."""
    return bool(re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', mac))

def get_ifconfig_output():
    """Run ifconfig and return its output as a UTF-8 string."""
    try:
        return subprocess.check_output(["ifconfig"], encoding="utf-8")
    except subprocess.CalledProcessError as e:
        return f"[red]Failed to execute ifconfig: {e}[/red]"

def get_interfaces(ifconfig_output):
    """Return a list of interface names from ifconfig output, excluding 'lo'."""
    interfaces = re.findall(r'^(\S+):', ifconfig_output, re.MULTILINE)
    return [iface for iface in interfaces if iface != "lo"]

def get_interface_block(interface):
    """Return the ifconfig output for the specified interface."""
    try:
        return subprocess.check_output(["ifconfig", interface], encoding="utf-8")
    except subprocess.CalledProcessError:
        return f"[red]No output found for interface: {interface}[/red]"

def get_interface_status(interface):
    """Return 'up' if the interface is up, otherwise 'down'."""
    output = get_interface_block(interface)
    return "up" if "UP" in output else "down"

def get_mac_from_ifconfig(interface):
    """Return the MAC address for the given interface, or None if not found."""
    output = get_interface_block(interface)
    match = re.search(r'(?:ether|HWaddr)\s*([0-9a-fA-F:]{17})', output)
    return match.group(1) if match else None

def get_mac_savefile(interface):
    """Return the path to the file where the original MAC is saved (in ~/.machanger)."""
    save_dir = Path.home() / ".machanger"
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir / f"{interface}.mac"

# ========== MAC Operations ==========
def save_original_mac(interface, mac, force_overwrite=False):
    """Save the original MAC address to a file, optionally overwriting."""
    savefile = get_mac_savefile(interface)
    if savefile.exists() and not force_overwrite:
        return
    try:
        with open(savefile, 'w', encoding='utf-8') as f:
            f.write(mac)
        print_colored(f"Original MAC address saved to {savefile}", 'success')
        log_action(f"Saved original MAC for {interface}: {mac}")
    except OSError as e:
        print_colored(f"Failed to save original MAC: {e}", 'error')

def load_original_mac(interface):
    """Load the original MAC address from the save file."""
    savefile = get_mac_savefile(interface)
    try:
        if savefile.exists():
            with open(savefile, 'r', encoding='utf-8') as f:
                return f.read().strip()
        print_colored(f"No saved original MAC address found for {interface} in {savefile}.", 'warning')
    except OSError as e:
        print_colored(f"Failed to load original MAC: {e}", 'error')
    return None

def list_interfaces():
    """List all interfaces and their MAC addresses."""
    ifconfig_output = get_ifconfig_output()
    interfaces = get_interfaces(ifconfig_output)
    if not interfaces:
        print_colored("No interfaces found!", 'error')
        return
    for iface in interfaces:
        mac = get_mac_from_ifconfig(iface)
        status = get_interface_status(iface)
        print_colored(f"{iface} - MAC: {mac} - Status: {status}", 'info')

def change_mac(interface, new_mac, verbose=False, force_overwrite=False):
    """Change the MAC address of the interface and print old/new MAC addresses."""
    old_mac = get_mac_from_ifconfig(interface)
    if old_mac:
        print_colored(f"Old MAC address: {old_mac}", 'warning')
        save_original_mac(interface, old_mac, force_overwrite=force_overwrite)
    else:
        print_colored("Could not read the current MAC address.", 'error')
    if not is_valid_mac(new_mac):
        print_colored(f"Invalid MAC address format: {new_mac}", 'error')
        return
    if old_mac and old_mac.lower() == new_mac.lower():
        print_colored("The new MAC address is the same as the current one. No change needed.", 'warning')
        return
    try:
        if verbose:
            print_colored(f"Bringing interface {interface} down...", 'verbose')
        subprocess.check_call(["sudo", "ifconfig", interface, "down"])
        if verbose:
            print_colored(f"Changing MAC address to {new_mac}...", 'verbose')
        subprocess.check_call(["sudo", "ifconfig", interface, "hw", "ether", new_mac])
        if verbose:
            print_colored(f"Bringing interface {interface} up...", 'verbose')
        subprocess.check_call(["sudo", "ifconfig", interface, "up"])
        log_action(f"Changed MAC for {interface} from {old_mac} to {new_mac}")
    except subprocess.CalledProcessError as e:
        if 'Permission denied' in str(e):
            print_colored("Permission denied. Try running with sudo.", 'error')
        else:
            print_colored(f"Failed to change MAC address: {e}", 'error')
        return
    new_mac_actual = get_mac_from_ifconfig(interface)
    if new_mac_actual:
        print_colored(f"New MAC address: {new_mac_actual}", 'success')
        if new_mac_actual.lower() == new_mac.lower():
            print_colored("MAC address was successfully changed!", 'success')
        else:
            print_colored("MAC address did not change as expected!", 'error')
    else:
        print_colored("Could not read the new MAC address.", 'error')

def restore_mac(interface, verbose=False):
    """Restore the original MAC address from the save file."""
    orig_mac = load_original_mac(interface)
    if not orig_mac:
        return
    print_colored(f"Restoring original MAC address: {orig_mac}", 'warning')
    try:
        if verbose:
            print_colored(f"Bringing interface {interface} down...", 'verbose')
        subprocess.check_call(["sudo", "ifconfig", interface, "down"])
        if verbose:
            print_colored(f"Restoring MAC address to {orig_mac}...", 'verbose')
        subprocess.check_call(["sudo", "ifconfig", interface, "hw", "ether", orig_mac])
        if verbose:
            print_colored(f"Bringing interface {interface} up...", 'verbose')
        subprocess.check_call(["sudo", "ifconfig", interface, "up"])
        log_action(f"Restored MAC for {interface} to {orig_mac}")
    except subprocess.CalledProcessError as e:
        if 'Permission denied' in str(e):
            print_colored("Permission denied. Try running with sudo.", 'error')
        else:
            print_colored(f"Failed to restore MAC address: {e}", 'error')
        return
    new_mac_actual = get_mac_from_ifconfig(interface)
    if new_mac_actual and new_mac_actual.lower() == orig_mac.lower():
        print_colored("MAC address was successfully restored!", 'success')
    else:
        print_colored("MAC address was not restored as expected!", 'error')

# ========== Extra Feature Utilities ==========
def check_privileges():
    """Check if the script is running with root privileges."""
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        print_colored("Warning: You are not running as root. Some operations may fail.", 'warning')

# --- MAC Generation ---
def generate_random_mac():
    """Generate a random, locally administered, unicast MAC address."""
    mac = [0x02, random.randint(0x00, 0x7f)] + [random.randint(0x00, 0xff) for _ in range(4)]
    return ':'.join(f"{octet:02x}" for octet in mac)

def generate_vendor_mac(oui):
    """Generate a random MAC address with the given OUI (first 3 bytes)."""
    try:
        parts = [int(x, 16) for x in oui.split(":")]
        if len(parts) != 3:
            raise ValueError
    except ValueError:
        print_colored("Invalid OUI format. Use format like 00:11:22", 'error')
        return None
    mac = parts + [random.randint(0x00, 0xff) for _ in range(3)]
    return ':'.join(f"{octet:02x}" for octet in mac)

# --- MAC History ---
HISTORY_FILE = Path.home() / ".machanger" / "history.json"
def log_mac_history(interface, old_mac, new_mac):
    """Log MAC changes to a history file."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    history = {}
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = {}
    entry = {
        "timestamp": datetime.now().isoformat(),
        "old_mac": old_mac,
        "new_mac": new_mac
    }
    history.setdefault(interface, []).append(entry)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)

def show_mac_history(interface):
    if not HISTORY_FILE.exists():
        print_colored("No MAC address history found.", 'warning')
        return
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)
    entries = history.get(interface, [])
    if not entries:
        print_colored(f"No history for interface {interface}.", 'warning')
        return
    for entry in entries:
        print_colored(f"[{entry['timestamp']}] {entry['old_mac']} -> {entry['new_mac']}", 'info')

# --- Restore All ---
def restore_all_interfaces(verbose=False):
    save_dir = Path.home() / ".machanger"
    restored = False
    for savefile in save_dir.glob("*.mac"):
        interface = savefile.stem
        print_colored(f"Restoring {interface}...", 'info')
        restore_mac(interface, verbose=verbose)
        restored = True
    if not restored:
        print_colored("No saved MAC addresses to restore.", 'warning')

# --- Dry Run ---
def dry_run_change_mac(interface, new_mac):
    old_mac = get_mac_from_ifconfig(interface)
    print_colored(f"[DRY RUN] Would change {interface} from {old_mac} to {new_mac}", 'info')

# --- Export/Import Profiles ---
PROFILE_DIR = Path.home() / ".machanger" / "profiles"
def export_profile(profile_name):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ifconfig_output = get_ifconfig_output()
    interfaces = get_interfaces(ifconfig_output)
    profile = {iface: get_mac_from_ifconfig(iface) for iface in interfaces}
    with open(PROFILE_DIR / f"{profile_name}.json", 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2)
    print_colored(f"Exported profile '{profile_name}'", 'success')

def import_profile(profile_name, verbose=False, dry_run=False):
    profile_path = PROFILE_DIR / f"{profile_name}.json"
    if not profile_path.exists():
        print_colored(f"Profile '{profile_name}' not found.", 'error')
        return
    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = json.load(f)
    for iface, mac in profile.items():
        if dry_run:
            dry_run_change_mac(iface, mac)
        else:
            change_mac(iface, mac, verbose=verbose)

# --- IP Command Fallback ---
def get_mac_from_ip(interface):
    try:
        output = subprocess.check_output(["ip", "link", "show", interface], encoding="utf-8")
        match = re.search(r"link/ether ([0-9a-fA-F:]{17})", output)
        return match.group(1) if match else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

# ========== Main Entry Point ==========
def main():
    """Main entry point for the MAC Changer tool."""
    console.print(Panel(Text("MAC Changer", style="bold green"), expand=False))
    args = get_arguments()

    if args.verbose:
        print_colored("Verbose mode enabled", 'verbose')

    if args.list_interfaces:
        list_interfaces()
        return

    if args.interface:
        print_colored(f"Interface: {args.interface}", 'info')

    if args.show_mac and not args.interface:
        print_colored("You must specify an interface with -i or --interface when using --show.", 'error')
        return

    if args.show_mac and args.interface:
        mac = get_mac_from_ifconfig(args.interface)
        if mac:
            print_colored(f"Current MAC for {args.interface}: {mac}", 'success')
        else:
            print_colored(f"Could not retrieve MAC for {args.interface}.", 'error')
        return

    if not args.interface:
        print_colored("You must specify an interface with -i or --interface (unless using --list).", 'error')
        return

    ifconfig_output = get_ifconfig_output()
    interfaces = get_interfaces(ifconfig_output)
    if args.interface not in interfaces:
        print_colored(f"Error: Interface '{args.interface}' does not exist!", 'error')
        print_colored(f"Available interfaces: {', '.join(interfaces)}", 'warning')
        return

    interface_block = get_interface_block(args.interface)
    mac = get_mac_from_ifconfig(args.interface)
    if mac:
        highlighted_block = re.sub(
            re.escape(mac),
            f"[bold green]{mac}[/bold green]",
            interface_block
        )
        console.print(Panel(Text.from_markup(highlighted_block), title=f"[cyan]{args.interface} info[/cyan]", expand=False))
    else:
        console.print(Panel(interface_block, title=f"[cyan]{args.interface} info[/cyan]", expand=False))

    if args.restore:
        restore_mac(args.interface, verbose=args.verbose)
    elif args.new_mac:
        change_mac(args.interface, args.new_mac, verbose=args.verbose, force_overwrite=args.force_overwrite)
    elif args.random:
        mac = generate_random_mac()
        print_colored(f"Generated random MAC: {mac}", 'info')
        change_mac(args.interface, mac, verbose=args.verbose, force_overwrite=args.force_overwrite)
    elif args.vendor:
        mac = generate_vendor_mac(args.vendor)
        if mac:
            print_colored(f"Generated vendor MAC: {mac}", 'info')
            change_mac(args.interface, mac, verbose=args.verbose, force_overwrite=args.force_overwrite)
    elif args.restore_all:
        restore_all_interfaces(verbose=args.verbose)
    elif args.history:
        show_mac_history(args.interface)
    elif args.dry_run:
        if args.new_mac:
            dry_run_change_mac(args.interface, args.new_mac)
        elif args.random:
            mac = generate_random_mac()
            print_colored(f"[DRY RUN] Would set random MAC: {mac}", 'info')
            dry_run_change_mac(args.interface, mac)
        elif args.vendor:
            mac = generate_vendor_mac(args.vendor)
            if mac:
                print_colored(f"[DRY RUN] Would set vendor MAC: {mac}", 'info')
                dry_run_change_mac(args.interface, mac)
        elif args.import_profile:
            import_profile(args.import_profile, verbose=args.verbose, dry_run=True)
        else:
            print_colored("[DRY RUN] No MAC change specified.", 'warning')
    elif args.export_profile:
        export_profile(args.export_profile)
    elif args.import_profile:
        import_profile(args.import_profile, verbose=args.verbose)
    else:
        print_colored("You must specify either --restore, --mac NEW_MAC, --show, or --list.", 'error')

if __name__ == "__main__":
    main()
