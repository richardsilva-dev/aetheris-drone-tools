# Arquitetura inicial

```text
Drone (câmera)
      │
      │ Wi-Fi / RTSP (somente leitura)
      ▼
PC Windows
      │
      ▼
OpenCV VideoCapture
      │
      ├── Exibição local
      ├── Estimativa de FPS
      ├── Gravação opcional
      └── Métricas da sessão
                │
                ▼
          reporting.py
                │
                ▼
          Relatório JSON
```

## Fronteiras entre componentes

- `video.py`: valida configuração e abre/lê o fluxo RTSP.
- `cli.py`: apresenta frames, mostra métricas, opcionalmente grava e coordena o relatório de sessão.
- `reporting.py`: serializa o relatório JSON e grava o arquivo de forma atômica.
- `tests/`: verifica funções auxiliares sem precisar conectar ao drone real.

## Relatório de sessão

A opção `--stats-json` gera um documento com versão de esquema, horário UTC de início, duração observada, URL de origem, frames recebidos, FPS médio calculado entre o primeiro e o último frame, status, motivo de encerramento, código de saída, caminho de gravação e eventual mensagem de erro.

O motivo `read_ended` indica apenas que a leitura deixou de entregar frames. A interface OpenCV utilizada não diferencia fim normal do fluxo e perda de conexão. O relatório não deve ser usado como diagnóstico definitivo da rede.

Uma futura integração de voo deverá ser um componente separado, com protocolo documentado, testes próprios, simulação e mecanismos de segurança.
