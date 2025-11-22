#!/bin/bash

# Podman Image Cleanup Script
# Löscht alle Podman Images (mit verschiedenen Optionen)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Podman Image Cleanup Script ===${NC}\n"

# Funktion: Hilfe anzeigen
show_help() {
    echo "Verwendung: $0 [OPTION]"
    echo ""
    echo "Optionen:"
    echo "  -a, --all        Alle Images löschen (inkl. verwendete)"
    echo "  -d, --dangling   Nur dangling Images löschen (ohne Tag)"
    echo "  -u, --unused     Nur unbenutzte Images löschen"
    echo "  -f, --force      Ohne Bestätigung löschen"
    echo "  -h, --help       Diese Hilfe anzeigen"
    echo ""
    exit 0
}

# Funktion: Images auflisten
list_images() {
    echo -e "${GREEN}Aktuelle Images:${NC}"
    podman images
    echo ""
}

# Funktion: Container stoppen
stop_containers() {
    if [ "$(podman ps -q)" ]; then
        echo -e "${YELLOW}Stoppe laufende Container...${NC}"
        podman stop $(podman ps -q)
    fi
}

# Funktion: Container entfernen
remove_containers() {
    if [ "$(podman ps -aq)" ]; then
        echo -e "${YELLOW}Entferne alle Container...${NC}"
        podman rm -f $(podman ps -aq)
    fi
}

# Funktion: Alle Images löschen
delete_all_images() {
    echo -e "${RED}Lösche ALLE Images...${NC}"
    stop_containers
    remove_containers
    podman rmi -af
    echo -e "${GREEN}Alle Images wurden gelöscht.${NC}"
}

# Funktion: Dangling Images löschen
delete_dangling() {
    echo -e "${YELLOW}Lösche dangling Images...${NC}"
    podman image prune -f
    echo -e "${GREEN}Dangling Images wurden gelöscht.${NC}"
}

# Funktion: Unbenutzte Images löschen
delete_unused() {
    echo -e "${YELLOW}Lösche unbenutzte Images...${NC}"
    podman image prune -af
    echo -e "${GREEN}Unbenutzte Images wurden gelöscht.${NC}"
}

# Funktion: Bestätigung einholen
confirm() {
    if [ "$FORCE" != "true" ]; then
        list_images
        read -p "Möchtest du wirklich fortfahren? (j/N): " choice
        case "$choice" in
            j|J|ja|Ja|JA ) return 0 ;;
            * ) echo "Abgebrochen."; exit 0 ;;
        esac
    fi
}

# Standardwerte
ACTION=""
FORCE="false"

# Parameter parsen
while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--all)      ACTION="all"; shift ;;
        -d|--dangling) ACTION="dangling"; shift ;;
        -u|--unused)   ACTION="unused"; shift ;;
        -f|--force)    FORCE="true"; shift ;;
        -h|--help)     show_help ;;
        *)             echo "Unbekannte Option: $1"; show_help ;;
    esac
done

# Interaktives Menü wenn keine Option angegeben
if [ -z "$ACTION" ]; then
    list_images
    echo "Was möchtest du löschen?"
    echo "  1) Alle Images (inkl. Container)"
    echo "  2) Nur dangling Images (ohne Tag)"
    echo "  3) Alle unbenutzten Images"
    echo "  4) Abbrechen"
    echo ""
    read -p "Wähle eine Option [1-4]: " choice
    
    case $choice in
        1) ACTION="all" ;;
        2) ACTION="dangling" ;;
        3) ACTION="unused" ;;
        4) echo "Abgebrochen."; exit 0 ;;
        *) echo "Ungültige Auswahl."; exit 1 ;;
    esac
fi

# Aktion ausführen
case $ACTION in
    all)
        confirm
        delete_all_images
        ;;
    dangling)
        delete_dangling
        ;;
    unused)
        confirm
        delete_unused
        ;;
esac

echo ""
echo -e "${GREEN}=== Fertig ===${NC}"
podman images