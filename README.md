# fairagro-playground

## Using go-template with Powershell

E.g:

<code>
get pods -n fairagro -o go-template='{{range .items}}{{printf \"%s\n\" .status.podIP}}{{end}}'
</code>
