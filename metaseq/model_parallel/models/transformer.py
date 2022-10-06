# Copyright (c) Meta Platforms, Inc. and affiliates. All Rights Reserved.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging

from metaseq.model_parallel.modules import (
    ModelParallelTransformerDecoderLayer,
    ModelParallelTransformerEncoderLayer,
)
from metaseq.models.transformer_decoder import TransformerDecoder
from metaseq.models.transformer_encoder import TransformerEncoder

try:
    from megatron.mpu import (
        copy_to_tensor_model_parallel_region,
        gather_from_tensor_model_parallel_region,
    )

    has_megatron_submodule = True
except (ImportError, ModuleNotFoundError):
    has_megatron_submodule = False


logger = logging.getLogger(__name__)


class ModelParallelTransformerEncoder(TransformerEncoder):
    """
    Model parallel Transformer encoder consisting of *args.encoder_layers* layers. Each layer
    is a :class:`ModelParallelTransformerEncoderLayer`.
    """

    def __init__(self, args, dictionary, embed_tokens):
        super().__init__(args, dictionary, embed_tokens)

        if args.no_final_layer_norm:
            self.layer_norm = None

    def build_encoder_layer(self, args):
        return ModelParallelTransformerEncoderLayer(args)


class ModelParallelTransformerDecoder(TransformerDecoder):
    """
    Model Parallel Transformer decoder consisting of *args.decoder_layers* layers. Each layer
    is a :class:`ModelParallelTransformerDecoderLayer`.
    """

    def build_base_decoder_layer(self, args, **kwargs):
        return ModelParallelTransformerDecoderLayer(args)

    def output_layer(self, features, **kwargs):
        """Project features to the vocabulary size."""

        features = copy_to_tensor_model_parallel_region(features)

        # project back to size of vocabulary
        x = self.output_projection(features)
        # Gather output if model in in inference mode (i.e. evallm or generation) cause both are not yet compatible with
        # parallel vocab embeddings
        if "vocab_parallel_cross_entropy" not in getattr(
            self.args, "criterion"
        ) or getattr(self, "inference", False):
            x = gather_from_tensor_model_parallel_region(x).contiguous()
        return x

    # This hook used as proxy for tracking state if model is in eval or generation mode.
    def make_generation_fast_(self, **unused):
        self.inference = True
