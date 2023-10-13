# Create a completion script for marzban-node
_marzban-node_completion() {
    local cur_word commands
    cur_word="${COMP_WORDS[COMP_CWORD]}"
    commands="add-container up down update dns certificate adjust-dns help tor install"

    case "${cur_word}" in
        *)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur_word}"))
            ;;
    esac
}

complete -F _marzban-node_completion marzban-node