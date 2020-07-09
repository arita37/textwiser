# Copyright 2019 FMR LLC <opensource@fidelity.com>
# SPDX-License-Identifer: Apache-2.0

from pathlib import Path

from bpemb import BPEmb
import flair
from flair.data import Sentence
from flair.embeddings import (
    WordEmbeddings as FlairWordEmbeddings,
    ELMoEmbeddings,
    FlairEmbeddings,
    CharacterEmbeddings,
)
from gensim.models import Word2Vec
import re
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel, AutoConfig

from textwiser.base import BaseFeaturizer
from textwiser.options import WordOptions
from textwiser.utils import device, split_tokenizer, Constants


def bytepair_tokenizer(docs, bp):
    vocab = bp.spm.EncodeAsIds
    if isinstance(docs, str):
        return torch.tensor(vocab(re.sub(r"\d", "0", docs.lower()))).to(device)
    return torch.tensor(vocab([re.sub(r"\d", "0", doc.lower()) for doc in docs])).to(device)


def transformers_loader(pretrained, **kwargs):
    config = AutoConfig.from_pretrained(pretrained, output_hidden_states=True, **kwargs)
    return AutoTokenizer.from_pretrained(pretrained), AutoModel.from_pretrained(pretrained, config=config).to(device)


def bytepair_pretrained_decoder(pretrained: str):
    opts = pretrained.split('_')
    lang, dim, vocab_size = 'en', 100, 10000
    if len(opts) > 2 and len(opts[2]) > 0:
        vocab_size = int(opts[2])
    if len(opts) > 1 and len(opts[1]) > 0:
        dim = int(opts[1])
    if len(opts[0]) > 0:
        lang = opts[0]
    return lang, dim, vocab_size


def bytepair_loader(pretrained: str, *args, **kwargs):
    """
    Pretrained options can be specified with the string ``<lang>_<dim>_<vocab_size>``
    Default options can be omitted like ``en``, ``en_100``, or ``en__10000``
    Defaults to ``en``, which is equal to ``en_100_10000``
    """
    lang, dim, vocab_size = bytepair_pretrained_decoder(pretrained)
    return BPEmb(lang=lang, dim=dim, vs=vocab_size, cache_dir=Path(flair.cache_root) / "embeddings", *args, **kwargs)


factory = {
    WordOptions.bytepair: bytepair_loader,
    WordOptions.char: CharacterEmbeddings,
    WordOptions.word2vec: FlairWordEmbeddings,
    WordOptions.flair: FlairEmbeddings,
    WordOptions.elmo: ELMoEmbeddings,
    WordOptions.bert: transformers_loader,
    WordOptions.gpt: transformers_loader,
    WordOptions.gpt2: transformers_loader,
    WordOptions.transformerXL: transformers_loader,
    WordOptions.xlnet: transformers_loader,
    WordOptions.xlm: transformers_loader,
    WordOptions.roberta: transformers_loader,
    WordOptions.distilbert: transformers_loader,
    WordOptions.ctrl: transformers_loader,
    WordOptions.albert: transformers_loader,
    WordOptions.t5: transformers_loader,
    WordOptions.xlm_roberta: transformers_loader,
    WordOptions.bart: transformers_loader,
    WordOptions.electra: transformers_loader,
    WordOptions.dialo_gpt: transformers_loader,
    WordOptions.longformer: transformers_loader,
}

pretrained_parameters = {
    WordOptions.bytepair: 'pretrained',
    WordOptions.word2vec: 'embeddings',
    WordOptions.flair: 'model',
    WordOptions.elmo: 'model',
    WordOptions.bert: 'pretrained',
    WordOptions.gpt: 'pretrained',
    WordOptions.gpt2: 'pretrained',
    WordOptions.transformerXL: 'pretrained',
    WordOptions.xlnet: 'pretrained',
    WordOptions.xlm: 'pretrained',
    WordOptions.roberta: 'pretrained',
    WordOptions.distilbert: 'pretrained',
    WordOptions.ctrl: 'pretrained',
    WordOptions.albert: 'pretrained',
    WordOptions.t5: 'pretrained',
    WordOptions.xlm_roberta: 'pretrained',
    WordOptions.bart: 'pretrained',
    WordOptions.electra: 'pretrained',
    WordOptions.dialo_gpt: 'pretrained',
    WordOptions.longformer: 'pretrained',
}

default_pretrained_options = {
    WordOptions.bytepair: 'en',
    WordOptions.word2vec: 'en',
    WordOptions.flair: 'news-forward-fast',
    WordOptions.elmo: 'original',
    WordOptions.bert: 'bert-base-uncased',
    WordOptions.gpt: 'openai-gpt',
    WordOptions.gpt2: 'gpt2-medium',
    WordOptions.transformerXL: 'transfo-xl-wt103',
    WordOptions.xlnet: 'xlnet-base-cased',
    WordOptions.xlm: 'xlm-mlm-en-2048',
    WordOptions.roberta: 'roberta-base',
    WordOptions.distilbert: 'distilbert-base-uncased',
    WordOptions.ctrl: 'ctrl',
    WordOptions.albert: 'albert-base-v2',
    WordOptions.t5: 't5-base',
    WordOptions.xlm_roberta: 'xlm-roberta-base',
    WordOptions.bart: 'facebook/bart-base',
    WordOptions.electra: 'google/electra-base-generator',
    WordOptions.dialo_gpt: 'microsoft/DialoGPT-small',
    WordOptions.longformer: 'allenai/longformer-base-4096',
}


def _get_and_init_word_embeddings(word_option: WordOptions, pretrained: str, **params):
    if word_option is WordOptions.flair:
        params['fine_tune'] = True

    if pretrained is not Constants.default_model:
        if word_option in pretrained_parameters:
            params[pretrained_parameters[word_option]] = pretrained
    else:
        if word_option in default_pretrained_options:
            params[pretrained_parameters[word_option]] = default_pretrained_options[word_option]

    return factory.get(word_option)(**params)


class _WordEmbeddings(BaseFeaturizer):
    def __init__(self, word_option: WordOptions, pretrained=Constants.default_model, sparse=True, tokenizer=None,
                 layers=-1, **kwargs):
        super(_WordEmbeddings, self).__init__()
        self.word_option = word_option
        self.pretrained = pretrained
        self.sparse = sparse
        self.tokenizer = tokenizer if tokenizer else split_tokenizer
        self.layers = [layers] if isinstance(layers, int) else layers
        self.init_args = kwargs
        self.model = None

    def _set_python_embeddings(self, keyed_vectors):
        self.vocab = keyed_vectors.vocab
        self.model = nn.Embedding.from_pretrained(
            torch.cat([torch.from_numpy(keyed_vectors.vectors),
                       torch.zeros([1, keyed_vectors.vector_size], requires_grad=True)]),
            freeze=False, sparse=self.sparse).to(device)

    def _set_bytepair_embeddings(self, bp):
        self.tokenizer = bytepair_tokenizer
        self.vocab = bp
        self.model = nn.Embedding.from_pretrained(
            torch.cat([torch.from_numpy(bp.emb.vectors),
                       torch.zeros([1, bp.emb.vector_size], requires_grad=True)]),
            freeze=False, sparse=self.sparse).to(device)
        bp.emb = None

    def _match_word(self, word: str):
        if word in self.vocab:
            return self.vocab[word].index
        elif word.lower() in self.vocab:
            return self.vocab[word.lower()].index
        elif (
            re.sub(r"\d", "#", word.lower()) in self.vocab
        ):
            return self.vocab[
                re.sub(r"\d", "#", word.lower())
            ].index
        elif (
            re.sub(r"\d", "0", word.lower()) in self.vocab
        ):
            return self.vocab[
                re.sub(r"\d", "0", word.lower())
            ].index
        else:
            return len(self.vocab)  # oov

    def _match_words(self, doc):
        return torch.tensor([self._match_word(word) for word in self.tokenizer(doc)], dtype=torch.long).to(device)

    def fit(self, x, y=None):
        if self.pretrained:
            self.model = _get_and_init_word_embeddings(self.word_option, pretrained=self.pretrained, **self.init_args)
            if self.word_option.is_from_transformers():
                self.tokenizer, self.model = self.model
            elif self.word_option is WordOptions.word2vec:
                self._set_python_embeddings(self.model.precomputed_word_embeddings)
            elif self.word_option is WordOptions.bytepair:
                self._set_bytepair_embeddings(self.model)
        else:
            if self.word_option is WordOptions.word2vec:  # Word2Vec is fittable
                w2v = Word2Vec([self.tokenizer(doc) for doc in x], **self.init_args)
                self._set_python_embeddings(w2v.wv)
            else:
                raise NotImplementedError("A {} model cannot be trained from scratch.".format(self.word_option))

    def forward(self, x):
        res = []
        for i, doc in enumerate(x):
            if self.word_option is WordOptions.word2vec:
                res.append(self.model(self._match_words(doc)))
            elif self.word_option is WordOptions.bytepair:
                res.append(self.model(self.tokenizer(doc, self.vocab)))
            elif self.word_option.is_from_transformers():
                if self.word_option == WordOptions.dialo_gpt:
                    encoded_inputs = self.tokenizer(doc, truncation=True, max_length=1024, return_tensors="pt")  # The max length for DialoGPT isn't properly configured
                    outs = self.model(**encoded_inputs)
                else:
                    encoded_inputs = self.tokenizer(doc, truncation=True, return_tensors="pt")
                    if self.word_option == WordOptions.t5:
                        outs = self.model(**encoded_inputs, decoder_input_ids=encoded_inputs['input_ids'])
                    else:
                        outs = self.model(**encoded_inputs)
                res.append(torch.cat([outs[-1][layer] for layer in self.layers], dim=-1)[0])
            else:
                sent = Sentence(doc)
                self.model.embed(sent)
                res.append(torch.stack([token.embedding for token in sent]).to(device))
        return res
