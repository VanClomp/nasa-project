# Shared helpers for the download scripts. Everything is saved under ../data next to the scripts folder.
ROOT="https://pds-atmospheres.nmsu.edu/PDS/data"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$HERE/data"
links() { curl -fsS --retry 3 "$1" | grep -o 'href="[^"?/][^"]*"' | sed 's/^href="//; s/"$//'; }
get()   { mkdir -p "$(dirname "$2")"; [ -s "$2" ] || curl -fsS --retry 3 -o "$2" "$1" || echo "FAILED: $1"; }
export -f get
# fetch_matching URL OUTDIR REGEX : download every file in one web folder whose name matches REGEX
fetch_matching() {
  mkdir -p "$2"
  links "$1" | grep -v '/$' | grep -E "$3" | xargs -P 6 -I{} bash -c 'get "$0" "$1"' "$1{}" "$2/{}"
}
