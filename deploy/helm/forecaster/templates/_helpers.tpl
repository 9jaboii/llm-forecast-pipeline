{{- define "forecaster.labels" -}}
app.kubernetes.io/name: forecaster
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "forecaster.securityContext.pod" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "forecaster.securityContext.container" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{- define "forecaster.envFrom" -}}
- configMapRef:
    name: forecaster-config
- secretRef:
    name: forecaster-secrets
{{- end -}}
