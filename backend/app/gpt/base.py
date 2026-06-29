from abc import ABC,abstractmethod
from typing import Callable, Optional

from app.models.gpt_model import GPTSource


class GPT(ABC):
    def summarize(
        self,
        source: GPTSource,
        on_partial: Optional[Callable[[str], None]] = None,
    ) -> str:
        '''

        :param source: 
        :return:
        '''
        pass
    def create_messages(self, segments:list,**kwargs)->list:
        pass
    def list_models(self):
        pass
