import torch
from torch import Tensor

from pytorch_lightning.utilities.cloud_io import load as pl_load

from .speaker_model import SpeakerModel
from . import MODEL_REGISTRY


class SpeakerEmbeddingModel(SpeakerModel):
    def __init__(self, configs, num_classes):
        super(SpeakerEmbeddingModel, self).__init__(configs, num_classes)

    def forward(self, inputs: torch.FloatTensor) -> Tensor:
        return self.model(inputs)

    def training_step(self, batch: tuple, batch_idx: int):
        if self.configs.criterion.name in ['adaptive_aamsoftmax'] and self.global_step == 0:
            self.log(
                "val_loss",
                15,
                on_step=True,
                on_epoch=False,
                prog_bar=True,
                logger=True,
            )
        if self.configs.criterion.name in ['adaptive_aamsoftmax']:
            self.criterion.step(self.global_step)
            self.log(
                "margin",
                self.criterion.classifier_.margin,
                on_step=True,
                on_epoch=False,
                prog_bar=True,
                logger=True,
            )
        X = batch['X']
        y = batch['y']
        embeddings = self.forward(X)
        loss = self.criterion(embeddings, y)
        return {
            'loss': loss
        }

    def validation_step(self, batch: tuple, batch_idx: int):
        X = batch['X']
        y = batch['y']
        embeddings = self.forward(X)
        loss = self.criterion(embeddings, y)
        self.log(
            "val_loss",
            loss,
            on_step=False,
            on_epoch=True,
            prog_bar=True,
            logger=True,
        )
        return {
            'val_loss': loss
        }

    def on_save_checkpoint(self, checkpoint):
        checkpoint["configs"] = self.configs
        checkpoint["num_classes"] = self.num_classes

    @classmethod
    def from_pretrained(cls, path_for_pl,
                        map_location=None,
                        strict=False, configs=None):
        loaded_checkpoint = pl_load(path_for_pl, map_location=map_location)
        model_name: str = loaded_checkpoint["configs"].model.name
        num_classes = loaded_checkpoint["num_classes"]
        if configs is not None:
            new_configs = configs
        else:
            new_configs = loaded_checkpoint["configs"]
        Klass = MODEL_REGISTRY[model_name]
        return Klass.load_from_checkpoint(
            path_for_pl,
            map_location=map_location,
            strict=strict,
            configs=new_configs,
            num_classes=num_classes
        )

    def to_torchscript(self, filepath):
        script = torch.jit.script(self.model)
        torch.jit.save(script, filepath)

    def make_embedding(self, feature):
        if self.model.training:
            self.model = self.model.eval()
        return self.model(feature).cpu().detach().numpy()
