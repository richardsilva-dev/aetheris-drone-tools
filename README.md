# Aetheris Drone Tools

Ferramentas iniciais para investigar a câmera e a conectividade de um drone de consumo usando Python. O primeiro componente recebe o fluxo RTSP da câmera em modo **somente leitura**.

> **Estado do projeto:** estágio inicial de investigação. A recepção de vídeo foi testada manualmente no VLC pelo mantenedor. A compatibilidade do protocolo de controle, o modelo exato do drone e a possibilidade de autonomia ainda não foram confirmados.

## Objetivos da primeira etapa

- Abrir o fluxo RTSP sem depender do aplicativo RC UFO.
- Exibir os frames recebidos usando OpenCV.
- Medir FPS aproximado durante a sessão.
- Opcionalmente gravar o vídeo recebido.
- Salvar métricas e o resultado da sessão em JSON para diagnóstico.
- Encerrar a captura com segurança ao pressionar `q` ou `Esc`.
- Manter a recepção de vídeo separada de qualquer futuro módulo de controle de voo.

## Evidências e configuração conhecida

| Item | Estado |
|---|---|
| Aplicativo usado | RC UFO, versão 1.9.7 (informado pelo mantenedor) |
| Rede Wi-Fi | `WIFI-UFO-a84c3c` (informado pelo mantenedor) |
| Endereço do dispositivo na rede | `192.168.1.1` (gateway observado pelo mantenedor) |
| Fluxo RTSP | `rtsp://192.168.1.1:7070/webcam` |
| VLC recebe a imagem | Testado manualmente com sucesso pelo mantenedor |
| Protocolo de comandos | Não identificado; não enviar comandos |
| Modelo exato / placa / firmware | Ainda não confirmados |

Os dados de rede podem mudar entre sessões ou variantes do drone. Configure a URL por argumento ou variável de ambiente em vez de presumir que ela será permanente.

## Requisitos

- Windows 10/11, Linux ou macOS.
- Python 3.10 ou superior.
- Acesso à rede Wi-Fi do drone.
- OpenCV (`opencv-python`).

## Instalação no Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Se a ativação do ambiente virtual for bloqueada pela política do PowerShell, execute os comandos usando diretamente `.\.venv\Scripts\python.exe`.

## Executar o receptor

Conecte o computador à rede Wi-Fi do drone e execute:

```powershell
python -m aetheris_drone --url rtsp://192.168.1.1:7070/webcam
```

Para gravar a sessão:

```powershell
python -m aetheris_drone --url rtsp://192.168.1.1:7070/webcam --record recordings/teste.mp4
```

Para gerar um relatório JSON com duração, quantidade de frames, FPS médio, resultado e motivo do encerramento:

```powershell
python -m aetheris_drone --stats-json recordings/diagnostico.json
```

As opções podem ser combinadas:

```powershell
python -m aetheris_drone --record recordings/teste.mp4 --stats-json recordings/diagnostico.json
```

O relatório registra `read_ended` quando o leitor OpenCV deixa de fornecer frames. A API `VideoCapture.read()` não permite distinguir, por si só, um fim normal do fluxo de uma desconexão; portanto, esse estado não deve ser interpretado como diagnóstico definitivo da causa.

Para encerrar, pressione `q` ou `Esc` na janela do vídeo.

## Estrutura

```text
aetheris-drone-tools/
├── docs/
│   ├── ARCHITECTURE.md
│   └── SAFETY.md
├── src/
│   └── aetheris_drone/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── reporting.py
│       └── video.py
├── tests/
│   ├── test_cli.py
│   ├── test_reporting.py
│   └── test_video.py
├── .gitignore
├── LICENSE
├── pyproject.toml
└── README.md
```

## Testes

```powershell
python -m pytest
```

Os testes atuais verificam configuração, cálculos auxiliares, fluxo da CLI e geração do relatório. Eles não substituem um teste de conexão com o drone real.

## Limites desta versão

- Não controla motores, hélices, direção, altitude ou trajetória.
- Não envia pacotes UDP/TCP ao drone.
- Não implementa reconhecimento de obstáculos, SLAM, VIO ou navegação autônoma.
- FPS medido é uma estimativa local da taxa de frames entregues pelo OpenCV; não é uma medição calibrada de latência ponta a ponta.
- A gravação depende dos codecs disponíveis na instalação do OpenCV.
- O relatório descreve o comportamento observado pelo processo; não determina a causa física ou de rede de uma interrupção RTSP.

## Próximas etapas

1. Testar estabilidade da recepção por sessões curtas e depois mais longas.
2. Comparar relatórios de sessões, observando FPS, duração e encerramentos.
3. Identificar com segurança os serviços de rede expostos pelo drone, sem enviar comandos.
4. Investigar documentação e hardware antes de qualquer integração de controle.
5. Avaliar simulação e mecanismos de parada/failsafe antes de testes físicos de autonomia.

## Licença

MIT. Consulte [LICENSE](LICENSE).
