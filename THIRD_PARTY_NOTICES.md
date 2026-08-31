# Third-party notices

## ECDICT

The distribution vocabulary seed contains entries adapted from [ECDICT](https://github.com/skywind3000/ECDICT).

MIT License

Copyright (c) 2025 Linwei

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# Piper build-time pronunciation tooling

The offline pronunciation pack is generated with Piper and the
`en_US-ljspeech-high` voice. Piper is used only as a build tool and is not
distributed in the application. The selected voice is trained from scratch on
the public-domain LJSpeech dataset. Generated audio is accompanied by a
versioned manifest containing the model and configuration checksums.

- Piper: https://github.com/OHF-Voice/piper1-gpl (GPL-3.0)
- Voice model card: https://huggingface.co/rhasspy/piper-voices/raw/main/en/en_US/ljspeech/high/MODEL_CARD
