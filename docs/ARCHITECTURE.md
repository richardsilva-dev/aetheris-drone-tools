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
      └── Gravação opcional
```

## Fronteiras entre componentes

- `video.py`: valida configuração e abre/lê o fluxo RTSP.
- `cli.py`: apresenta frames, mostra métricas e opcionalmente grava.
- `tests/`: verifica funções auxiliares sem precisar conectar ao drone.

O receptor não implementa nem importa uma camada de controle. Uma futura integração de voo deverá ser um componente separado, com protocolo documentado, testes próprios, simulação e mecanismos de segurança.
