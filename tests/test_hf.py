"""Real local tiny-transformer tests. Random models verify plumbing, not efficacy."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ('torch', 'transformers', 'peft'))


@unittest.skipUnless(AVAILABLE, 'optional torch/transformers/peft dependencies are not installed')
class TinyTransformerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast
        from patchlens.data import load_dataset, fixture_path
        torch.set_num_threads(1)
        torch.manual_seed(23)
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.base = cls.root / 'random-tiny-bert'
        cls.base.mkdir()
        vocabulary = ['[PAD]', '[UNK]', '[CLS]', '[SEP]', '[MASK]', 'function', 'return', 'const', 'input', 'value', 'db', 'query', 'eval', 'textContent', 'innerHTML', '(', ')', '{', '}', ';', '.', '=', '"']
        (cls.base / 'vocab.txt').write_text('\n'.join(vocabulary))
        tokenizer = BertTokenizerFast(vocab_file=str(cls.base / 'vocab.txt'), do_lower_case=False)
        tokenizer.save_pretrained(cls.base)
        BertForSequenceClassification(BertConfig(vocab_size=len(vocabulary), hidden_size=24, num_hidden_layers=1,
            num_attention_heads=2, intermediate_size=32, max_position_embeddings=128, num_labels=2)).save_pretrained(cls.base, safe_serialization=True)
        cls.samples = load_dataset(fixture_path())

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_lora_trains_and_round_trips_real_predictions(self):
        import numpy as np
        from safetensors.torch import load_file
        from patchlens.hf_training import train, predict_trained, TrainingConfig
        output = self.root / 'lora'
        metadata, predictions, embeddings, history = train(self.samples, str(self.base), output,
            TrainingConfig(epochs=1, batch_pairs=3, max_length=64, rank=2))
        self.assertLess(metadata['trainable_parameters'], metadata['total_parameters'])
        self.assertEqual(len(embeddings), 48)
        self.assertTrue(history[0]['contrastive'] > 0)
        checkpoint = load_file(str(output / 'checkpoint/adapter_model.safetensors'))
        self.assertTrue(any(k.endswith('lora_B.weight') and float(v.abs().sum()) > 0 for k, v in checkpoint.items()))
        actual = predict_trained(self.samples, output / 'checkpoint', base_model=str(self.base), max_length=64)
        np.testing.assert_allclose([p['score'] for p in predictions], [p['score'] for p in actual], atol=1e-7)

    def test_frozen_and_supervised_train_and_save(self):
        from patchlens.hf_training import train, TrainingConfig
        for mode in ('frozen', 'supervised'):
            config = TrainingConfig(mode=mode, contrastive_weight=0., positive_weight=1., epochs=1, max_length=64)
            metadata, predictions, _, _ = train(self.samples, str(self.base), self.root / mode, config)
            self.assertEqual(len(predictions), 48)
            self.assertEqual(metadata['training_ids'], [s.id for s in self.samples if s.split == 'train'])

    def test_contrastive_loss_attracts_views_and_masks_same_label(self):
        import torch
        from patchlens.hf_training import paired_loss
        good = torch.tensor([[1., 0.], [-1., 0.], [1., .01], [-1., .01]], requires_grad=True)
        bad = torch.tensor([[1., 0.], [-1., 0.], [-1., .01], [1., .01]])
        labels = torch.tensor([0, 1, 0, 1])
        loss = paired_loss(good, labels, .15)
        self.assertLess(float(loss.detach()), float(paired_loss(bad, labels, .15)))
        loss.backward()
        self.assertTrue(torch.isfinite(good.grad).all())

    def test_real_causal_generation_saves_unexecuted_text(self):
        import torch
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast
        from patchlens.generation import generate
        from patchlens.io import load_jsonl
        base = self.root / 'random-tiny-gpt2'
        base.mkdir()
        vocab = {'<pad>': 0, '<unk>': 1, '<eos>': 2, 'function': 3, 'return': 4, 'value': 5, ';': 6}
        token = Tokenizer(WordLevel(vocab, unk_token='<unk>'))
        token.pre_tokenizer = Whitespace()
        tokenizer = PreTrainedTokenizerFast(tokenizer_object=token, unk_token='<unk>', pad_token='<pad>', eos_token='<eos>')
        tokenizer.save_pretrained(base)
        torch.manual_seed(5)
        GPT2LMHeadModel(GPT2Config(vocab_size=len(vocab), n_positions=64, n_embd=16, n_layer=1, n_head=2,
            eos_token_id=2, pad_token_id=0)).save_pretrained(base, safe_serialization=True)
        result = generate([{'id': 'smoke', 'prompt': 'function value', 'assumptions': 'Random model; no quality claim'}],
                          str(base), self.root / 'generation', max_new_tokens=8)
        self.assertEqual(result['status'], 'completed')
        row = load_jsonl(self.root / 'generation/generations.jsonl')[0]
        self.assertEqual(row['security_review'], 'not_reviewed')
        self.assertTrue((self.root / 'generation/src/smoke.js').exists())


if __name__ == '__main__': unittest.main()
