"""py2app entry point for the Murti app bundle.

Kept tiny on purpose: it just hands off to the real menu-bar app in
`murti.app`. py2app freezes/aliases this script as the bundle's main program.
"""
from murti.app import main

if __name__ == "__main__":
    main()
