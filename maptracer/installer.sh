#!/usr/bin/env bash

set -e # exit on error

PREFIX=/usr/local
LIB_DIR="$PREFIX"/lib
INCLUDE_DIR="$PREFIX"/include

NAME=maptracer
HEADER="$NAME".h
HEA_SRC=./"$HEADER"
LIB_SRC=./obj-intel64/lib"$NAME".so
LD_CONF=local_"$NAME".conf
VER_MAJOR=1
VER_MINOR=0

SONAME=lib"$NAME".so
SONAME_MAJ=lib"$NAME".so."$VER_MAJOR"
REALNAME="$SONAME_MAJ"."$VER_MINOR"

run() {
    echo "$*"
    eval "$@"
}

install_tool(){
    remove_tool
    run sudo install -d "$LIB_DIR"
    run sudo install -m 0755 --no-target-directory "$LIB_SRC" "$LIB_DIR/$REALNAME"
    run sudo rm -f "$LIB_DIR/$SONAME"
    run sudo ln -s "$REALNAME" "$LIB_DIR/$SONAME"
    run sudo ln -s "$REALNAME" "$LIB_DIR/$SONAME_MAJ"
    run sudo install -d "$INCLUDE_DIR"
    run sudo install -m 0644 "$HEA_SRC" "$INCLUDE_DIR"
    run 'echo "/usr/local/lib" | sudo tee "/etc/ld.so.conf.d/$LD_CONF" >/dev/null'
    run sudo ldconfig
}

remove_tool(){
    run sudo rm -f "$LIB_DIR/$SONAME" "$LIB_DIR/$SONAME_MAJ" "$LIB_DIR/$REALNAME" "$INCLUDE_DIR/$HEADER" "/etc/ld.so.conf.d/$LD_CONF"
    run sudo ldconfig
}

test_tool(){
    echo "ldconfig -p | grep $NAME"
    if ! ldconfig -p | grep $NAME | sed 's/^[ \t]*//'; then
        echo "Couldn't find the library."
        exit 1
    fi
    echo "ls $INCLUDE_DIR/$HEADER"
    if ! /bin/ls "$INCLUDE_DIR/$HEADER"; then
         echo "Couldn't find the header file."
         exit 1
    fi
}

if [[ $# -eq 0 ]]; then
    action=install
elif [[ $# -eq 1 ]]; then
    action="$1"
else
    echo "USAGE $(basename $0) install|remove|test"
    exit 1
fi

echo
case "$action" in
    'install')
        echo "Installing $NAME..."
        install_tool && echo "$NAME installed!"
        ;;
    'remove')
        echo "Removing $NAME..."
        remove_tool && echo "$NAME removed!"
        ;;
    'test')
        echo "Checking for $NAME..."
        test_tool && echo "'$NAME' seems to be correctly installed!"
        ;;
    *)
        echo "Unknown action '$action'."
        echo "USAGE $(basename $0) install|remove|test"
        exit 1
esac
