"""Run an official Iqra'Eval s3prl baseline checkpoint (e.g. IqraEval/Iqra_wav2vec2_base) without s3prl.

The checkpoint holds only the trained parts: layer weights over a frozen wav2vec2-base, a projector and a
2-layer BiLSTM CTC head. We rebuild that head here (shapes from the checkpoint, layout from s3prl's
downstream/ctc RNNs model) and load the checkpoint with weights_only=True, so no pickled code runs.
"""
import argparse

import torch
from torch import nn
from transformers import Wav2Vec2Model

UPSTREAM = {"wav2vec2_base_960": "facebook/wav2vec2-base"}  # s3prl name -> the same weights on Hugging Face


class _RNN(nn.Module):
    def __init__(self, d_in, dim):
        super().__init__()
        self.layer = nn.LSTM(d_in, dim, batch_first=True, bidirectional=True)
        self.pj = nn.Linear(2 * dim, 2 * dim)

    def forward(self, x):
        return torch.tanh(self.pj(self.layer(x)[0]))


class IqraBaseline(nn.Module):
    def __init__(self, ckpt_path, vocab_path, device):
        super().__init__()
        torch.serialization.add_safe_globals([argparse.Namespace])
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        down = {k: v for k, v in ckpt["Downstream"].items() if k != "best_score"}
        self.upstream = Wav2Vec2Model.from_pretrained(UPSTREAM[ckpt["Args"].upstream])
        self.layer_weights = nn.Parameter(ckpt["Featurizer"]["weights"])
        self.projector = nn.Linear(*down["projector.weight"].shape[::-1])
        self.rnns = nn.ModuleList([_RNN(down[f"model.rnns.{i}.layer.weight_ih_l0"].shape[1], 1024) for i in range(2)])
        self.linear = nn.Linear(*down["model.linear.weight"].shape[::-1])
        self.load_state_dict({**{k.removeprefix("model."): v for k, v in down.items()},
                              **{f"upstream.{k}": v for k, v in self.upstream.state_dict().items()},
                              "layer_weights": self.layer_weights.data})
        # s3prl's word-mode text encoder puts <pad> (the CTC blank), <eos>, <unk> before the vocab file lines
        self.vocab = ["<pad>", "<eos>", "<unk>"] + open(vocab_path, encoding="utf-8").read().split()
        self.device = device
        self.to(device).eval()

    @torch.inference_mode()
    def recognize(self, samples) -> list[str]:
        wav = torch.as_tensor(samples, device=self.device)[None]
        hidden = torch.stack(self.upstream(wav, output_hidden_states=True).hidden_states)  # (13, 1, T, 768)
        x = (torch.softmax(self.layer_weights, 0)[:, None, None, None] * hidden).sum(0)
        x = self.projector(x)
        for rnn in self.rnns:
            x = rnn(x)
        ids = torch.unique_consecutive(self.linear(x).argmax(-1)[0]).tolist()
        return [self.vocab[i] for i in ids if i > 2]
