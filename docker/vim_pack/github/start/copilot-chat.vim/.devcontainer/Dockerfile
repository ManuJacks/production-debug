FROM alpine:latest
RUN apk update && apk add git vim neovim neovim-doc curl bash python3 py3-pip

RUN mkdir -p ~/.vim/bundle
RUN mkdir -p ~/.config/nvim
RUN git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim

RUN ln -sf python3 /usr/bin/python
RUN pip install vim-vint --break-system-packages