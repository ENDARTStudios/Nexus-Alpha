# Utiliza uma imagem Python leve e oficial do Linux
FROM python:3.10-slim

# Cria um usuário não-root (Exigência do Hugging Face para containers gratuitos)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Define o diretório de trabalho dentro do container
WORKDIR $HOME/app

# Copia o arquivo de dependências e instala os pacotes Python (runtime leve do Space)
COPY --chown=user requirements-hf.txt $HOME/app/requirements-hf.txt
RUN pip install --no-cache-dir --upgrade -r requirements-hf.txt

# Copia o restante do código do projeto para o container
COPY --chown=user . $HOME/app

# Expõe a porta padrão obrigatória do Hugging Face Spaces
EXPOSE 7860

# Comando para iniciar a API FastAPI usando o servidor Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]