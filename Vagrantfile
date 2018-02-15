# -*- coding: utf-8 -*-
# -*- mode: ruby -*-
# vi: set ft=ruby :

# Wymagane pluginy:
#  * vagrant-hostmanager
#  * vagrant-cachier


Vagrant.configure(2) do |config|

  if Vagrant.has_plugin?("vagrant-hostmanager")
      config.hostmanager.enabled = true
      config.hostmanager.manage_host = true
      config.hostmanager.ignore_private_ip = false
      config.hostmanager.include_offline = true
   end

  config.vm.define "staging" do |staging|
      staging.vm.box = "ubuntu/xenial64"
      staging.vm.box_check_update = false

      staging.vm.provider "virtualbox" do |vb|
        vb.cpus = 4
        vb.memory = 3072
      end

      staging.vm.hostname = 'bpp-staging'
      if Vagrant.has_plugin?("vagrant-hostmanager")
          staging.hostmanager.aliases = %w(bpp-staging.localnet)
      end

      if Vagrant.has_plugin?("vagrant-timezone")
      	 staging.timezone.value = :host
      end

      staging.vm.network "private_network", ip: "192.168.111.101"
      staging.vm.provision "shell", inline: "sudo dd if=/dev/zero of=/swapfile bs=1M count=1024"
      staging.vm.provision "shell", inline: "sudo mkswap /swapfile"
      staging.vm.provision "shell", inline: "sudo swapon /swapfile"
      staging.vm.provision "shell", inline: "sudo apt update"      
      staging.vm.provision "shell", inline: "sudo apt install python-minimal -y"

      if Vagrant.has_plugin?("vagrant-cachier")
        staging.cache.scope = :box
        staging.cache.enable :apt
        staging.cache.enable :npm
      end

  end

end
